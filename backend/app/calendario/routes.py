from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.calendario.schemas import AbrangenciaEvento, EventoCreate, EventoRead, EventoUpdate, TipoEvento
from app.calendario.service import consultar_eventos
from app.database.models import Empresa, EventoCalendario
from app.database.session import get_db

router = APIRouter(prefix="/calendario", tags=["Calendário"])


def validar_empresa(payload: EventoCreate, db: Session):
    if payload.empresa_id is not None and db.get(Empresa, payload.empresa_id) is None:
        raise HTTPException(status_code=422, detail="Empresa não encontrada.")


@router.get("", response_model=list[EventoRead])
def listar_eventos(ano: int = Query(default=date.today().year, ge=1, le=9999),
                   tipo: TipoEvento | None = None, abrangencia: AbrangenciaEvento | None = None,
                   db: Session = Depends(get_db)):
    return consultar_eventos(db, ano, tipo, abrangencia)


@router.get("/{evento_id}", response_model=EventoRead)
def obter_evento(evento_id: int, db: Session = Depends(get_db)):
    evento = db.get(EventoCalendario, evento_id)
    if evento is None:
        raise HTTPException(status_code=404, detail="Data não encontrada.")
    return evento


@router.post("", response_model=EventoRead, status_code=201)
def criar_evento(payload: EventoCreate, db: Session = Depends(get_db)):
    validar_empresa(payload, db)
    evento = EventoCalendario(**payload.model_dump())
    db.add(evento)
    db.commit()
    db.refresh(evento)
    return evento


@router.patch("/{evento_id}", response_model=EventoRead)
def atualizar_evento(evento_id: int, payload: EventoUpdate, db: Session = Depends(get_db)):
    evento = obter_evento(evento_id, db)
    dados = {campo: getattr(evento, campo) for campo in EventoCreate.model_fields}
    dados.update(payload.model_dump(exclude_unset=True))
    try:
        validado = EventoCreate.model_validate(dados)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=jsonable_encoder(exc.errors(include_context=False))) from exc
    validar_empresa(validado, db)
    for campo, valor in validado.model_dump().items():
        setattr(evento, campo, valor)
    db.commit()
    db.refresh(evento)
    return evento
