from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.apuracao.service import apurar_competencia
from app.database.session import get_db


router = APIRouter(prefix="/apuracao", tags=["Apuração"])


@router.get("")
def obter_apuracao(
    competencia_id: int = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    resultado = apurar_competencia(db, competencia_id)
    if not resultado:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")
    return resultado


@router.get("/{competencia_id}")
def obter_apuracao_por_rota(competencia_id: int, db: Session = Depends(get_db)) -> dict:
    resultado = apurar_competencia(db, competencia_id)
    if not resultado:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")
    return resultado
