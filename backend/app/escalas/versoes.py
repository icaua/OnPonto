"""Configuração histórica; nenhuma edição de JSON de versão existente."""
from calendar import monthrange
from dataclasses import fields
from datetime import date,time,timedelta
import json

from fastapi import HTTPException
from app.database.models import EscalaVersao,Competencia,MarcacaoPonto,Funcionario
from app.dominio.contratos import RegraVigente
from app.banco_horas.politica import hoje_local

CAMPOS=tuple(f.name for f in fields(RegraVigente) if f.name not in {"id","versao_id","jornada_dia_minutos"})


def configuracao(escala):
    dados={campo:getattr(escala,campo,None) for campo in CAMPOS}
    return json.dumps(dados,ensure_ascii=False,sort_keys=True,default=lambda v:v.isoformat())


def regra_da_versao(versao):
    dados=json.loads(versao.configuracao_json)
    for campo in CAMPOS:
        if campo.startswith("horario_") and dados.get(campo): dados[campo]=time.fromisoformat(dados[campo])
    return RegraVigente(id=versao.escala_id,versao_id=versao.id,**dados)


def garantir_inicial(db,escala,desde=None):
    existente=db.query(EscalaVersao).filter_by(escala_id=escala.id).order_by(EscalaVersao.numero).first()
    if existente: return existente
    item=EscalaVersao(escala_id=escala.id,numero=1,vigente_desde=desde,
        configuracao_json=configuracao(escala),origem="cadastro_vigencia_explicita" if desde else "legado_vigencia_desconhecida")
    db.add(item);db.flush()
    return item


def nova_versao(db,escala,dados,desde=None):
    anterior=garantir_inicial(db,escala)
    atual=db.query(EscalaVersao).filter_by(escala_id=escala.id).order_by(EscalaVersao.numero.desc()).first()
    texto=json.dumps({campo:dados.get(campo) for campo in CAMPOS},ensure_ascii=False,sort_keys=True,default=lambda v:v.isoformat())
    if texto==atual.configuracao_json: return None
    if desde is None:
        desde=hoje_local()+timedelta(days=1)
        if atual.vigente_desde is not None:
            desde=max(desde,atual.vigente_desde+timedelta(days=1))
    if atual.vigente_desde is not None and desde<=atual.vigente_desde:
        raise HTTPException(409,"A vigência deve ser posterior à última versão; versões anteriores não podem ser reescritas.")
    from app.competencias.dependencias import exigir_referencias_editaveis
    exigir_referencias_editaveis(db,empresa_id=escala.empresa_id,inicio=desde)
    for competencia in db.query(Competencia).filter_by(empresa_id=escala.empresa_id,status="fechada"):
        fim=date(competencia.ano,competencia.mes,monthrange(competencia.ano,competencia.mes)[1])
        if fim>=desde:
            raise HTTPException(409,"A vigência alcança competência fechada. Escolha data futura ou reabra explicitamente antes de revisar.")
    atual.vigente_ate=desde-timedelta(days=1)
    db.flush()
    nova=EscalaVersao(escala_id=escala.id,numero=atual.numero+1,vigente_desde=desde,
        configuracao_json=texto,origem="alteracao_explicita")
    db.add(nova);db.flush()
    # Apenas situação/revisão humana muda; evidências e horários permanecem.
    from app.funcionarios.historico_escalas import ResolvedorEscalas
    from app.marcacoes.auditoria import registrar_evento
    resolvedor=ResolvedorEscalas(db,escala.empresa_id)
    funcionarios={f.id:f for f in db.query(Funcionario).filter_by(empresa_id=escala.empresa_id)}
    for m in db.query(MarcacaoPonto).join(Competencia).filter(
            Competencia.empresa_id==escala.empresa_id,Competencia.status!="fechada",MarcacaoPonto.data>=desde):
        vinculada=resolvedor.escala_no_dia(funcionarios[m.funcionario_id],m.data)
        if vinculada and vinculada.id==escala.id:
            m.conferido=False
            registrar_evento(m,"Regra de escala versionada",f"Revisão necessária após versão {nova.numero}, vigência {desde.isoformat()}.",{})
            m.competencia.status="em_conferencia"
    return nova
