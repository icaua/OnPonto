from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.banco_horas.politica import hoje_local
from app.database.models import Escala, EscalaVersao, Funcionario, HistoricoVinculoEscala, MarcacaoPonto


class ResolvedorEscalas:
    """Histórico da empresa válido apenas durante a operação atual."""

    def __init__(self, db, empresa_id):
        self.versoes={}
        self.regras={}
        for versao in db.query(EscalaVersao).join(Escala).filter(Escala.empresa_id==empresa_id).order_by(EscalaVersao.numero.desc()):
            self.versoes.setdefault(versao.escala_id,[]).append(versao)
        self.vinculos = {}
        for vinculo in (db.query(HistoricoVinculoEscala)
                .join(Funcionario, Funcionario.id == HistoricoVinculoEscala.funcionario_id)
                .filter(Funcionario.empresa_id == empresa_id)
                .options(joinedload(HistoricoVinculoEscala.escala))
                .order_by(HistoricoVinculoEscala.vigente_desde.desc(), HistoricoVinculoEscala.id.desc())):
            self.vinculos.setdefault(vinculo.funcionario_id, []).append(vinculo)
        # Referências fortes mantêm as escalas atuais no mapa de identidade da sessão.
        self.escalas = (db.query(Escala).join(Funcionario, Funcionario.escala_id == Escala.id)
                        .filter(Funcionario.empresa_id == empresa_id).all())

    def escala_no_dia(self, funcionario, dia):
        vinculos = self.vinculos.get(funcionario.id, [])
        for vinculo in vinculos:
            if vinculo.vigente_desde <= dia and (vinculo.vigente_ate is None or vinculo.vigente_ate >= dia):
                return vinculo.escala
        primeiro = vinculos[-1] if vinculos else None
        if primeiro and dia < primeiro.vigente_desde:
            return primeiro.escala
        return funcionario.escala if not primeiro else None

    def regra_no_dia(self,funcionario,dia):
        from app.escalas.versoes import regra_da_versao
        from app.apuracao.adaptadores import regra
        escala=self.escala_no_dia(funcionario,dia)
        if escala is None: return None
        versoes=self.versoes.get(escala.id,[])
        for versao in versoes:
            if (versao.vigente_desde is None or versao.vigente_desde<=dia) and (versao.vigente_ate is None or versao.vigente_ate>=dia):
                if versao.id not in self.regras: self.regras[versao.id]=regra_da_versao(versao)
                return self.regras[versao.id].para_dia(dia)
        if versoes: return None
        chave=("legado",escala.id)
        if chave not in self.regras: self.regras[chave]=regra(escala)
        return self.regras[chave].para_dia(dia)


def registrar_vinculo_inicial(db, funcionario):
    if funcionario.escala_id is None or db.query(HistoricoVinculoEscala.id).filter_by(funcionario_id=funcionario.id).first():
        return
    primeira = db.query(MarcacaoPonto.data).filter_by(funcionario_id=funcionario.id).order_by(MarcacaoPonto.data).first()
    datas = [hoje_local(), funcionario.created_at.date() if funcionario.created_at else hoje_local()]
    if funcionario.data_admissao:
        datas.append(funcionario.data_admissao)
    if primeira:
        datas.append(primeira[0])
    db.add(HistoricoVinculoEscala(funcionario_id=funcionario.id, escala_id=funcionario.escala_id,
                                 vigente_desde=min(datas)))
    db.flush()


def registrar_vinculos_iniciais(db, funcionarios):
    from sqlalchemy import func
    ids=[f.id for f in funcionarios if f.escala_id is not None]
    if not ids: return
    existentes={id for id, in db.query(HistoricoVinculoEscala.funcionario_id).filter(HistoricoVinculoEscala.funcionario_id.in_(ids)).distinct()}
    primeiras=dict(db.query(MarcacaoPonto.funcionario_id,func.min(MarcacaoPonto.data)).filter(
        MarcacaoPonto.funcionario_id.in_(ids)).group_by(MarcacaoPonto.funcionario_id).all())
    for f in funcionarios:
        if f.escala_id is None or f.id in existentes: continue
        datas=[hoje_local(),f.created_at.date() if f.created_at else hoje_local()]
        if f.data_admissao: datas.append(f.data_admissao)
        if primeiras.get(f.id): datas.append(primeiras[f.id])
        db.add(HistoricoVinculoEscala(funcionario_id=f.id,escala_id=f.escala_id,vigente_desde=min(datas)))
    db.flush()


def trocar_vinculo(db, funcionario, nova_escala_id):
    registrar_vinculo_inicial(db, funcionario)
    hoje = hoje_local()
    for vinculo in db.query(HistoricoVinculoEscala).filter_by(funcionario_id=funcionario.id, vigente_ate=None):
        vinculo.vigente_ate = hoje
    if nova_escala_id is not None:
        db.add(HistoricoVinculoEscala(funcionario_id=funcionario.id, escala_id=nova_escala_id, vigente_desde=hoje))


def escala_no_dia(db, funcionario, dia):
    vinculo = (db.query(HistoricoVinculoEscala)
        .filter(HistoricoVinculoEscala.funcionario_id == funcionario.id,
                HistoricoVinculoEscala.vigente_desde <= dia,
                or_(HistoricoVinculoEscala.vigente_ate.is_(None), HistoricoVinculoEscala.vigente_ate >= dia))
        # No dia da troca os limites são inclusivos; o novo vínculo prevalece.
        .order_by(HistoricoVinculoEscala.vigente_desde.desc(), HistoricoVinculoEscala.id.desc()).first())
    if vinculo:
        return db.get(Escala, vinculo.escala_id)
    primeiro = (db.query(HistoricoVinculoEscala).filter_by(funcionario_id=funcionario.id)
        .order_by(HistoricoVinculoEscala.vigente_desde, HistoricoVinculoEscala.id).first())
    # Cadastros sem admissão começam no dia do cadastro; arquivos anteriores
    # continuam usando a escala inicial. Uma lacuna posterior não recebe fallback.
    if primeiro and dia < primeiro.vigente_desde:
        return db.get(Escala, primeiro.escala_id)
    return funcionario.escala if not primeiro else None
