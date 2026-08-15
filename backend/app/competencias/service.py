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


def contar_pendencias_operacionais(db: Session, competencia_id: int) -> int:
    resultado = apurar_competencia(db, competencia_id)
    return len(resultado["pendencias"]) if resultado else 0


def mensagem_pendencias(total_pendencias: int) -> str:
    if total_pendencias == 1:
        return "1 registro ainda precisa de conferência."
    return f"{total_pendencias} registros ainda precisam de conferência."


def sincronizar_status_competencia(db: Session, competencia: Competencia) -> int:
    """Sincroniza o estado editável a partir das marcações persistidas na sessão."""

    if competencia.status == "fechada":
        return contar_pendencias_operacionais(db, competencia.id)

    db.flush()
    if contar_marcacoes(db, competencia.id) == 0:
        competencia.status = "aberta"
        return 0

    total_pendencias = contar_pendencias_operacionais(db, competencia.id)
    competencia.status = "em_conferencia" if total_pendencias else "conferida"
    return total_pendencias
