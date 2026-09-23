from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.competencias.service import exigir_competencia_editavel, sincronizar_status_competencia
from app.database.models import Competencia, Funcionario, MarcacaoPonto
from app.database.session import get_db
from app.marcacoes.schemas import MarcacaoCreate, MarcacaoRead, MarcacaoUpdate, ORIGENS, STATUS_DIA
from app.marcacoes.auditoria import estado, registrar_alteracao, validar_sequencia


router = APIRouter(prefix="/marcacoes", tags=["Marcações de ponto"])


def validar_status_origem(status_dia: str | None, origem: str | None) -> None:
    if status_dia is not None and status_dia not in STATUS_DIA:
        raise HTTPException(status_code=400, detail="Status do dia inválido.")
    if origem is not None and origem not in ORIGENS:
        raise HTTPException(status_code=400, detail="Origem inválida.")


def validar_vinculos(db: Session, competencia_id: int, funcionario_id: int) -> Competencia:
    competencia = db.get(Competencia, competencia_id)
    if not competencia:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")

    funcionario = db.get(Funcionario, funcionario_id)
    if not funcionario:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")

    if funcionario.empresa_id != competencia.empresa_id:
        raise HTTPException(status_code=400, detail="Funcionário não pertence à empresa da competência.")
    return competencia


def validar_data_competencia(
    competencia: Competencia,
    data_marcacao: date,
) -> None:
    if (data_marcacao.year, data_marcacao.month) != (
        competencia.ano,
        competencia.mes,
    ):
        raise HTTPException(
            status_code=400,
            detail="A data da marcação não pertence à competência informada.",
        )


@router.get("", response_model=list[MarcacaoRead])
def listar_marcacoes(
    competencia_id: int = Query(...),
    funcionario_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[MarcacaoPonto]:
    query = db.query(MarcacaoPonto).filter(MarcacaoPonto.competencia_id == competencia_id)
    if funcionario_id:
        query = query.filter(MarcacaoPonto.funcionario_id == funcionario_id)
    return query.order_by(MarcacaoPonto.data.asc(), MarcacaoPonto.funcionario_id.asc()).all()


@router.post("", response_model=MarcacaoRead, status_code=status.HTTP_201_CREATED)
def salvar_marcacao(payload: MarcacaoCreate, db: Session = Depends(get_db)) -> MarcacaoPonto:
    validar_status_origem(payload.status_dia, payload.origem)
    competencia = validar_vinculos(db, payload.competencia_id, payload.funcionario_id)
    exigir_competencia_editavel(competencia)
    validar_data_competencia(competencia, payload.data)

    marcacao = (
        db.query(MarcacaoPonto)
        .filter(
            MarcacaoPonto.competencia_id == payload.competencia_id,
            MarcacaoPonto.funcionario_id == payload.funcionario_id,
            MarcacaoPonto.data == payload.data,
        )
        .first()
    )

    antes = estado(marcacao) if marcacao else None
    if marcacao:
        for campo, valor in payload.model_dump().items():
            if campo == "origem" and marcacao.arquivo_origem_id is not None:
                continue
            setattr(marcacao, campo, valor)
    else:
        marcacao = MarcacaoPonto(**payload.model_dump())
        db.add(marcacao)

    validar_sequencia(marcacao)
    registrar_alteracao(marcacao, antes)
    try:
        sincronizar_status_competencia(db, competencia)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Não foi possível salvar a marcação.") from exc
    db.refresh(marcacao)
    return marcacao


@router.get("/{marcacao_id}", response_model=MarcacaoRead)
def obter_marcacao(marcacao_id: int, db: Session = Depends(get_db)) -> MarcacaoPonto:
    marcacao = db.get(MarcacaoPonto, marcacao_id)
    if not marcacao:
        raise HTTPException(status_code=404, detail="Marcação não encontrada.")
    return marcacao


@router.patch("/{marcacao_id}", response_model=MarcacaoRead)
def atualizar_marcacao(
    marcacao_id: int,
    payload: MarcacaoUpdate,
    db: Session = Depends(get_db),
) -> MarcacaoPonto:
    marcacao = db.get(MarcacaoPonto, marcacao_id)
    if not marcacao:
        raise HTTPException(status_code=404, detail="Marcação não encontrada.")
    competencia_original = db.get(Competencia, marcacao.competencia_id)
    if not competencia_original:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")
    exigir_competencia_editavel(competencia_original)

    dados = payload.model_dump(exclude_unset=True)
    validar_status_origem(dados.get("status_dia"), dados.get("origem"))

    competencia_id = dados.get("competencia_id", marcacao.competencia_id)
    funcionario_id = dados.get("funcionario_id", marcacao.funcionario_id)
    competencia_destino = validar_vinculos(db, competencia_id, funcionario_id)
    exigir_competencia_editavel(competencia_destino)

    antes = estado(marcacao)
    for campo, valor in dados.items():
        setattr(marcacao, campo, valor)
    if dados and marcacao.origem == "calendario":
        marcacao.origem = "manual"

    validar_sequencia(marcacao)
    registrar_alteracao(marcacao, antes)
    try:
        sincronizar_status_competencia(db, competencia_original)
        if competencia_destino.id != competencia_original.id:
            sincronizar_status_competencia(db, competencia_destino)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Não foi possível atualizar a marcação.") from exc
    db.refresh(marcacao)
    return marcacao
