from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.competencias.schemas import (
    CompetenciaAcaoRead,
    CompetenciaCreate,
    CompetenciaRead,
    CompetenciaUpdate,
    FechamentoCompetenciaRequest,
)
from app.competencias.service import (
    contar_marcacoes,
    contar_pendencias_operacionais,
    exigir_competencia_editavel,
    mensagem_pendencias,
    sincronizar_status_competencia,
)
from app.database.models import Competencia, Empresa
from app.database.session import get_db


router = APIRouter(prefix="/competencias", tags=["Competências"])
FUSO_HORARIO_LOCAL = ZoneInfo("America/Sao_Paulo")


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
    if not db.get(Empresa, payload.empresa_id):
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")

    competencia = Competencia(**payload.model_dump(), status="aberta", data_fechamento=None)
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
    exigir_competencia_editavel(competencia)

    dados = payload.model_dump(exclude_unset=True)
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


@router.post("/{competencia_id}/fechar", response_model=CompetenciaAcaoRead)
def fechar_competencia(
    competencia_id: int,
    payload: FechamentoCompetenciaRequest,
    db: Session = Depends(get_db),
) -> dict:
    competencia = db.get(Competencia, competencia_id)
    if not competencia:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")
    if competencia.status == "fechada":
        raise HTTPException(status_code=409, detail="A competência já está fechada.")

    total_marcacoes = contar_marcacoes(db, competencia.id)
    total_pendencias = sincronizar_status_competencia(db, competencia)
    fechamento_excepcional = competencia.status != "conferida"

    if fechamento_excepcional and not payload.confirmar_pendencias:
        if total_pendencias:
            codigo = "competencia_com_pendencias"
            mensagem = mensagem_pendencias(total_pendencias)
        elif total_marcacoes == 0:
            codigo = "competencia_sem_registros"
            mensagem = "A competência não possui registros processados para fechamento."
        else:
            codigo = "competencia_nao_conferida"
            mensagem = "A competência ainda não está conferida."
        raise HTTPException(
            status_code=409,
            detail={
                "codigo": codigo,
                "mensagem": mensagem,
                "total_pendencias": total_pendencias,
            },
        )

    competencia.status = "fechada"
    competencia.data_fechamento = datetime.now(FUSO_HORARIO_LOCAL).date()
    db.commit()
    db.refresh(competencia)

    if fechamento_excepcional:
        if total_pendencias:
            mensagem = (
                f"Competência fechada excepcionalmente com {total_pendencias} "
                f"{'registro pendente' if total_pendencias == 1 else 'registros pendentes'}."
            )
        elif total_marcacoes == 0:
            mensagem = "Competência fechada excepcionalmente sem registros processados."
        else:
            mensagem = "Competência fechada excepcionalmente antes da conclusão da conferência."
    else:
        mensagem = "Competência fechada."

    return {
        "id": competencia.id,
        "status": competencia.status,
        "data_fechamento": competencia.data_fechamento,
        "total_pendencias": total_pendencias,
        "fechamento_excepcional": fechamento_excepcional,
        "mensagem": mensagem,
    }


@router.post("/{competencia_id}/reabrir", response_model=CompetenciaAcaoRead)
def reabrir_competencia(
    competencia_id: int,
    db: Session = Depends(get_db),
) -> dict:
    competencia = db.get(Competencia, competencia_id)
    if not competencia:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")
    if competencia.status != "fechada":
        raise HTTPException(status_code=409, detail="A competência não está fechada.")

    total_marcacoes = contar_marcacoes(db, competencia.id)
    total_pendencias = contar_pendencias_operacionais(db, competencia.id)
    competencia.status = "em_conferencia" if total_marcacoes else "aberta"
    competencia.data_fechamento = None
    db.commit()
    db.refresh(competencia)

    return {
        "id": competencia.id,
        "status": competencia.status,
        "data_fechamento": competencia.data_fechamento,
        "total_pendencias": total_pendencias,
        "fechamento_excepcional": False,
        "mensagem": "Competência reaberta.",
    }
