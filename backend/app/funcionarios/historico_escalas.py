from sqlalchemy import or_

from app.banco_horas.politica import hoje_local
from app.database.models import Escala, HistoricoVinculoEscala, MarcacaoPonto


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
    return db.get(Escala, vinculo.escala_id) if vinculo else None
