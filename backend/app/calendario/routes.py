from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.calendario.schemas import AbrangenciaEvento, EventoCreate, EventoRead, EventoUpdate, TipoEvento
from app.calendario.service import consultar_eventos
from app.database.models import Empresa, EventoCalendario
from app.database.session import get_db
from app.database.transacoes import atomica

router = APIRouter(prefix="/calendario", tags=["Calendário"])


def validar_empresa(payload: EventoCreate, db: Session):
    if payload.empresa_id is not None and db.get(Empresa, payload.empresa_id) is None:
        raise HTTPException(status_code=422, detail="Empresa não encontrada.")


def validar_referencias_dsr(db, evento):
    if evento.tipo!="FERIADO": return
    from app.database.models import DependenciaFechamento, FechamentoVersao, Competencia, MarcacaoPonto
    from app.calendario.service import abrange_empresa, data_no_ano
    for data, empresa_id in db.query(MarcacaoPonto.data,Competencia.empresa_id).select_from(DependenciaFechamento).join(
            MarcacaoPonto,MarcacaoPonto.id==DependenciaFechamento.marcacao_id).join(
            FechamentoVersao,FechamentoVersao.id==DependenciaFechamento.fechamento_id).join(
            Competencia,Competencia.id==FechamentoVersao.competencia_id).filter(
            Competencia.status=="fechada",Competencia.versao_fechamento==FechamentoVersao.numero).distinct():
        if data_no_ano(evento,data.year)==data and abrange_empresa(evento,db.get(Empresa,empresa_id)):
            raise HTTPException(409,"O feriado participa de referência DSR fechada. Reabra a competência antes de alterar o calendário.")


def sincronizar_calendario(db, eventos):
    from calendar import monthrange
    from datetime import timedelta
    from app.database.models import Competencia
    from app.calendario.service import abrange_empresa, data_no_ano
    from app.competencias.service import sincronizar_status_competencia
    db.flush()
    for c in db.query(Competencia).filter(Competencia.status!="fechada"):
        inicio=date(c.ano,c.mes,1)-timedelta(days=6)
        fim=date(c.ano,c.mes,monthrange(c.ano,c.mes)[1])+timedelta(days=6)
        if any(e.tipo=="FERIADO" and abrange_empresa(e,c.empresa) and any(
                (d:=data_no_ano(e,ano)) is not None and inicio<=d<=fim for ano in range(inicio.year,fim.year+1)) for e in eventos):
            sincronizar_status_competencia(db,c)


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
@atomica
def criar_evento(payload: EventoCreate, db: Session = Depends(get_db)):
    validar_empresa(payload, db)
    evento = EventoCalendario(**payload.model_dump())
    validar_referencias_dsr(db,evento)
    db.add(evento)
    sincronizar_calendario(db,[evento])
    db.commit()
    db.refresh(evento)
    return evento


@router.patch("/{evento_id}", response_model=EventoRead)
@atomica
def atualizar_evento(evento_id: int, payload: EventoUpdate, db: Session = Depends(get_db)):
    evento = obter_evento(evento_id, db)
    validar_referencias_dsr(db,evento)
    anterior=EventoCalendario(**{campo:getattr(evento,campo) for campo in EventoCreate.model_fields})
    dados = {campo: getattr(evento, campo) for campo in EventoCreate.model_fields}
    dados.update(payload.model_dump(exclude_unset=True))
    try:
        validado = EventoCreate.model_validate(dados)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=jsonable_encoder(exc.errors(include_context=False))) from exc
    validar_empresa(validado, db)
    validar_referencias_dsr(db,EventoCalendario(**validado.model_dump()))
    for campo, valor in validado.model_dump().items():
        setattr(evento, campo, valor)
    sincronizar_calendario(db,[anterior,evento])
    db.commit()
    db.refresh(evento)
    return evento
