from calendar import monthrange
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database.models import Competencia, OcorrenciaFuncionario
from app.database.session import UPLOADS_DIR, get_db
from app.ocorrencias.schemas import OcorrenciaCreate, OcorrenciaRead, OcorrenciaUpdate
from app.ocorrencias.service import auditar, consultar, estado, iniciar_escrita, sincronizar_abertas, validar_fechadas, validar_sobreposicao
from app.banco_horas.folgas import validar_folga

router = APIRouter(prefix="/ocorrencias", tags=["Ocorrências e afastamentos"])


def obter(db, ocorrencia_id, incluir_excluidas=False):
    registro = db.get(OcorrenciaFuncionario, ocorrencia_id)
    if not registro or (registro.excluido_em and not incluir_excluidas):
        raise HTTPException(404, "Ocorrência não encontrada.")
    return registro


@router.get("", response_model=list[OcorrenciaRead])
def listar(empresa_id: int | None = None, funcionario_id: int | None = None,
           data_inicio: date | None = None, data_fim: date | None = None,
           competencia_id: int | None = None, incluir_excluidas: bool = False,
           db: Session = Depends(get_db)):
    if competencia_id:
        competencia = db.get(Competencia, competencia_id)
        if not competencia:
            raise HTTPException(404, "Competência não encontrada.")
        if empresa_id is not None and empresa_id != competencia.empresa_id:
            raise HTTPException(400, "Competência não pertence à empresa selecionada.")
        empresa_id = competencia.empresa_id
        data_inicio = date(competencia.ano, competencia.mes, 1)
        data_fim = date(competencia.ano, competencia.mes, monthrange(competencia.ano, competencia.mes)[1])
    if data_inicio and data_fim and data_fim < data_inicio:
        raise HTTPException(422, "O fim do filtro não pode ser anterior ao início.")
    return consultar(db, funcionario_id, empresa_id, data_inicio, data_fim, incluir_excluidas)


@router.post("", response_model=OcorrenciaRead, status_code=201)
def criar(payload: OcorrenciaCreate, db: Session = Depends(get_db)):
    iniciar_escrita(db)
    validar_fechadas(db, payload)
    validar_sobreposicao(db, payload)
    validar_folga(db, payload)
    registro = OcorrenciaFuncionario(**payload.model_dump())
    db.add(registro)
    auditar(registro, "criacao", None)
    sincronizar_abertas(db, payload)
    db.commit()
    db.refresh(registro)
    return registro


@router.get("/{ocorrencia_id}", response_model=OcorrenciaRead)
def consultar_uma(ocorrencia_id: int, db: Session = Depends(get_db)):
    return obter(db, ocorrencia_id)


@router.get("/{ocorrencia_id}/historico")
def historico(ocorrencia_id: int, db: Session = Depends(get_db)):
    return obter(db, ocorrencia_id, incluir_excluidas=True).historico


@router.patch("/{ocorrencia_id}", response_model=OcorrenciaRead)
def editar(ocorrencia_id: int, payload: OcorrenciaUpdate, db: Session = Depends(get_db)):
    iniciar_escrita(db)
    registro = obter(db, ocorrencia_id)
    original = OcorrenciaCreate.model_validate({c: getattr(registro, c) for c in OcorrenciaCreate.model_fields})
    try:
        dados = OcorrenciaCreate.model_validate({**original.model_dump(), **payload.model_dump(exclude_unset=True)})
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_context=False)) from exc
    validar_fechadas(db, original)
    validar_fechadas(db, dados)
    validar_sobreposicao(db, dados, registro.id)
    validar_folga(db, dados, registro.id)
    antes = estado(registro)
    for campo, valor in dados.model_dump().items():
        setattr(registro, campo, valor)
    auditar(registro, "alteracao", antes)
    sincronizar_abertas(db, original, dados)
    db.commit()
    db.refresh(registro)
    return registro


@router.delete("/{ocorrencia_id}", status_code=204)
def excluir(ocorrencia_id: int, db: Session = Depends(get_db)):
    iniciar_escrita(db)
    registro = obter(db, ocorrencia_id)
    validar_fechadas(db, registro)
    antes = estado(registro)
    registro.excluido_em = datetime.now(timezone.utc)
    auditar(registro, "exclusao", antes)
    sincronizar_abertas(db, registro)
    db.commit()
    return Response(status_code=204)


@router.post("/{ocorrencia_id}/anexo", response_model=OcorrenciaRead)
def anexar(ocorrencia_id: int, arquivo: UploadFile = File(...), db: Session = Depends(get_db)):
    destino = None
    try:
        iniciar_escrita(db)
        registro = obter(db, ocorrencia_id)
        validar_fechadas(db, registro)
        nome = Path((arquivo.filename or "documento").replace("\\", "/")).name
        extensao = Path(nome).suffix.lower()
        if extensao not in {".pdf", ".png", ".jpg", ".jpeg"}:
            raise HTTPException(400, "Anexe PDF, PNG ou JPG.")
        pasta = UPLOADS_DIR / "ocorrencias" / str(registro.id)
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / (uuid4().hex + extensao)
        total = 0
        with destino.open("wb") as buffer:
            while trecho := arquivo.file.read(1024 * 1024):
                total += len(trecho)
                if total > 25 * 1024 * 1024:
                    raise HTTPException(413, "O anexo excede o limite de 25 MB.")
                buffer.write(trecho)
        if not total:
            raise HTTPException(400, "O anexo está vazio.")
        antes = estado(registro)
        registro.anexo_caminho = destino.relative_to(UPLOADS_DIR).as_posix()
        registro.anexo_nome = nome[:255]
        auditar(registro, "anexo", antes)
        db.commit()
    except Exception:
        db.rollback()
        if destino:
            destino.unlink(missing_ok=True)
        raise
    finally:
        arquivo.file.close()
    db.refresh(registro)
    return registro


@router.get("/{ocorrencia_id}/anexo")
def baixar_anexo(ocorrencia_id: int, db: Session = Depends(get_db)):
    registro = obter(db, ocorrencia_id)
    if not registro.anexo_caminho:
        raise HTTPException(404, "Ocorrência sem anexo.")
    caminho = (UPLOADS_DIR / registro.anexo_caminho).resolve()
    if not caminho.is_relative_to(UPLOADS_DIR.resolve()):
        raise HTTPException(400, "Referência de anexo inválida.")
    if not caminho.is_file():
        raise HTTPException(404, "Anexo não encontrado no armazenamento.")
    return FileResponse(caminho, filename=registro.anexo_nome, media_type="application/octet-stream")
