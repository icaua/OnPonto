import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.competencias.service import exigir_competencia_editavel, sincronizar_status_competencia
from app.database.models import Competencia, Funcionario, MarcacaoPonto
from app.database.session import get_db
from app.marcacoes.schemas import DesconsideracaoBatida, MarcacaoCreate, MarcacaoRead, MarcacaoUpdate, ORIGENS, STATUS_DIA
from app.apuracao.service import apurar_competencia
from app.ocorrencias.service import iniciar_escrita
from pydantic import BaseModel, Field
from app.marcacoes.auditoria import estado, registrar_alteracao, registrar_evento, validar_sequencia


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
    validar_conferencia(db, marcacao)
    registrar_alteracao(marcacao, antes)
    try:
        sincronizar_status_competencia(db, competencia)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Não foi possível salvar a marcação.") from exc
    db.refresh(marcacao)
    return marcacao



class ConferenciaLote(BaseModel):
    competencia_id: int
    marcacoes_ids: list[int] = Field(min_length=1, max_length=1000)


def validar_conferencia(db, marcacao):
    if not marcacao.conferido:
        return
    db.flush()
    resultado = apurar_competencia(db, marcacao.competencia_id, incluir_banco=False)
    dia = next((d for d in resultado["marcacoes"] if d["id"] == marcacao.id), None)
    if dia is None or dia["problema"]:
        db.rollback()
        raise HTTPException(409, detail={"codigo": "dia_com_problema", "mensagem": dia["pendencia_motivo"] if dia else "Registro fora do vínculo."})


@router.post("/conferir-lote")
def conferir_lote(payload: ConferenciaLote, db: Session = Depends(get_db)):
    iniciar_escrita(db)
    competencia = db.get(Competencia, payload.competencia_id)
    if not competencia:
        raise HTTPException(404, "Competência não encontrada.")
    exigir_competencia_editavel(competencia)
    resultado = apurar_competencia(db, competencia.id, incluir_banco=False)
    por_id = {d["id"]: d for d in resultado["marcacoes"]}
    conferidos, problemas = [], []
    for id in dict.fromkeys(payload.marcacoes_ids):
        dia = por_id.get(id)
        if dia is None:
            raise HTTPException(422, "Seleção contém registro que não pertence à competência ou ao vínculo.")
        if dia["problema"]:
            problemas.append({"id": id, "motivo": dia["pendencia_motivo"]})
            continue
        marcacao = db.get(MarcacaoPonto, id)
        antes = estado(marcacao)
        marcacao.conferido = True
        registrar_alteracao(marcacao, antes)
        conferidos.append(id)
    sincronizar_status_competencia(db, competencia)
    db.commit()
    return {"conferidos": conferidos, "problemas": problemas, "total_conferidos": len(conferidos), "total_problemas": len(problemas)}


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
    validar_conferencia(db, marcacao)
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


def marcacao_para_decisao_de_batida(db: Session, marcacao_id: int) -> tuple[MarcacaoPonto, Competencia, list]:
    iniciar_escrita(db)
    marcacao = db.get(MarcacaoPonto, marcacao_id)
    if not marcacao:
        raise HTTPException(status_code=404, detail="Marcação não encontrada.")
    competencia = db.get(Competencia, marcacao.competencia_id)
    exigir_competencia_editavel(competencia)
    if marcacao.conferido:
        raise HTTPException(status_code=409, detail="Reabra a conferência do dia antes de alterar o destino de uma batida.")
    try:
        brutas = json.loads(marcacao.batidas_originais or "[]")
    except ValueError:
        brutas = []
    return marcacao, competencia, [str(item) for item in brutas] if isinstance(brutas, list) else []


@router.post("/{marcacao_id}/batidas-desconsideradas", response_model=MarcacaoRead)
def desconsiderar_batida(marcacao_id: int, payload: DesconsideracaoBatida, db: Session = Depends(get_db)) -> MarcacaoPonto:
    """Tira uma batida bruta da contagem (ex.: batida duplicada). A batida original é preservada."""
    marcacao, competencia, brutas = marcacao_para_decisao_de_batida(db, marcacao_id)
    if payload.indice >= len(brutas):
        raise HTTPException(status_code=422, detail="Batida original não encontrada neste dia.")
    atuais = marcacao.batidas_desconsideradas
    if any(item["indice"] == payload.indice for item in atuais):
        raise HTTPException(status_code=409, detail="Esta batida já está desconsiderada.")
    horario = brutas[payload.indice]
    atuais.append({"indice": payload.indice, "horario": horario, "justificativa": payload.justificativa,
                   "em": datetime.now(timezone.utc).isoformat()})
    marcacao.batidas_desconsideradas_json = json.dumps(sorted(atuais, key=lambda item: item["indice"]), ensure_ascii=False)
    registrar_evento(marcacao, "Batida desconsiderada", f"Batida original {horario} desconsiderada: {payload.justificativa}",
                     {"batidas_desconsideradas": {"antes": None, "depois": {"indice": payload.indice, "horario": horario}}})
    sincronizar_status_competencia(db, competencia)
    db.commit()
    db.refresh(marcacao)
    return marcacao


@router.delete("/{marcacao_id}/batidas-desconsideradas/{indice}", response_model=MarcacaoRead)
def restaurar_batida(marcacao_id: int, indice: int, db: Session = Depends(get_db)) -> MarcacaoPonto:
    marcacao, competencia, _ = marcacao_para_decisao_de_batida(db, marcacao_id)
    atuais = marcacao.batidas_desconsideradas
    removida = next((item for item in atuais if item["indice"] == indice), None)
    if removida is None:
        raise HTTPException(status_code=404, detail="Esta batida não está desconsiderada.")
    restantes = [item for item in atuais if item["indice"] != indice]
    marcacao.batidas_desconsideradas_json = json.dumps(restantes, ensure_ascii=False) if restantes else None
    registrar_evento(marcacao, "Batida restaurada", f"Batida original {removida['horario']} voltou a exigir destino.",
                     {"batidas_desconsideradas": {"antes": {"indice": indice, "horario": removida["horario"]}, "depois": None}})
    sincronizar_status_competencia(db, competencia)
    db.commit()
    db.refresh(marcacao)
    return marcacao
