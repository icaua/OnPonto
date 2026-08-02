from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.competencias.schemas import CompetenciaCreate, CompetenciaRead, CompetenciaUpdate, STATUS_COMPETENCIA
from app.database.models import Competencia, Empresa
from app.database.session import get_db


router = APIRouter(prefix="/competencias", tags=["Competências"])


def validar_status(status_competencia: str) -> None:
    if status_competencia not in STATUS_COMPETENCIA:
        raise HTTPException(status_code=400, detail="Status de competência inválido.")


@router.get("", response_model=list[CompetenciaRead])
def listar_competencias(
    empresa_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Competencia]:
    query = db.query(Competencia)
    if empresa_id:
        query = query.filter(Competencia.empresa_id == empresa_id)
    return query.order_by(Competencia.ano.desc(), Competencia.mes.desc()).all()


@router.post("", response_model=CompetenciaRead, status_code=status.HTTP_201_CREATED)
def criar_competencia(payload: CompetenciaCreate, db: Session = Depends(get_db)) -> Competencia:
    validar_status(payload.status)
    if not db.get(Empresa, payload.empresa_id):
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")

    competencia = Competencia(**payload.model_dump())
    db.add(competencia)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Competência já cadastrada para esta empresa.") from exc
    db.refresh(competencia)
    return competencia


@router.get("/{competencia_id}", response_model=CompetenciaRead)
def obter_competencia(competencia_id: int, db: Session = Depends(get_db)) -> Competencia:
    competencia = db.get(Competencia, competencia_id)
    if not competencia:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")
    return competencia


@router.patch("/{competencia_id}", response_model=CompetenciaRead)
def atualizar_competencia(
    competencia_id: int,
    payload: CompetenciaUpdate,
    db: Session = Depends(get_db),
) -> Competencia:
    competencia = db.get(Competencia, competencia_id)
    if not competencia:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")

    dados = payload.model_dump(exclude_unset=True)
    if "status" in dados and dados["status"] is not None:
        validar_status(dados["status"])
    if "empresa_id" in dados and not db.get(Empresa, dados["empresa_id"]):
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")

    for campo, valor in dados.items():
        setattr(competencia, campo, valor)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Competência já cadastrada para esta empresa.") from exc
    db.refresh(competencia)
    return competencia
