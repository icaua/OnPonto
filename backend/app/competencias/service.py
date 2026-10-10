from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.apuracao.service import apurar_competencia
from app.database.models import Competencia, MarcacaoPonto


MENSAGEM_COMPETENCIA_FECHADA = (
    "A competência está fechada. Reabra a competência antes de alterar dados."
)


def exigir_competencia_editavel(competencia: Competencia) -> None:
    if competencia.status == "fechada":
        raise HTTPException(status_code=409, detail=MENSAGEM_COMPETENCIA_FECHADA)


def contar_marcacoes(db: Session, competencia_id: int) -> int:
    return (
        db.query(MarcacaoPonto)
        .filter(MarcacaoPonto.competencia_id == competencia_id)
        .count()
    )


def contar_pendencias_operacionais(
    db: Session,
    competencia_id: int,
    *,
    gerar_calendario: bool = False,
) -> int:
    from app.apuracao.triagem import consultar_triagem
    if gerar_calendario:
        from app.apuracao.service import gerar_dias_faltantes
        competencia=db.get(Competencia,competencia_id)
        if competencia: gerar_dias_faltantes(db,competencia)
    resultado=consultar_triagem(db,competencia_id,persistir=True)
    contagens=resultado.get("operacional",{}) if resultado else {}
    return sum(contagens.get(k,0) for k in ("problemas","aguardando_conferencia","conflitos_importacao","analises_pendentes","dias_sem_registro"))


def sincronizar_abertas_empresa(db, empresa_id):
    db.flush()
    for competencia in db.query(Competencia).filter(Competencia.empresa_id==empresa_id,Competencia.status!="fechada"):
        sincronizar_status_competencia(db,competencia)


def mensagem_pendencias(total_pendencias: int) -> str:
    if total_pendencias == 1:
        return "1 registro ainda precisa de conferência."
    return f"{total_pendencias} registros ainda precisam de conferência."


def sincronizar_status_competencia(
    db: Session,
    competencia: Competencia,
    *,
    gerar_calendario: bool = False,
) -> int:
    """Sincroniza o estado editável a partir das marcações persistidas na sessão."""

    if competencia.status == "fechada":
        return contar_pendencias_operacionais(
            db,
            competencia.id,
            gerar_calendario=gerar_calendario,
        )

    db.flush()
    if gerar_calendario:
        total_pendencias = contar_pendencias_operacionais(
            db,
            competencia.id,
            gerar_calendario=True,
        )
        if contar_marcacoes(db, competencia.id) == 0:
            competencia.status = "aberta"
            return 0
        competencia.status = "em_conferencia" if total_pendencias else "conferida"
        return total_pendencias
    if contar_marcacoes(db, competencia.id) == 0:
        competencia.status = "aberta"
        return 0

    total_pendencias = contar_pendencias_operacionais(db, competencia.id)
    competencia.status = "em_conferencia" if total_pendencias else "conferida"
    return total_pendencias
