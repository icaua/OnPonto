import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.arquivos.schemas import ArquivoRead
from app.competencias.service import exigir_competencia_editavel
from app.database.models import ArquivoRecebido, Competencia
from app.database.session import BACKEND_DIR, UPLOADS_DIR, get_db
from app.importadores.armazenamento import salvar_arquivo_original
from app.seguranca.arquivos import verificar_hash


router = APIRouter(prefix="/arquivos", tags=["Arquivos recebidos"])

EXTENSOES_PERMITIDAS = {".txt", ".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".csv"}


def nome_seguro(nome: str) -> str:
    base = Path(nome).name.strip() or "arquivo"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base)


@router.get("", response_model=list[ArquivoRead])
def listar_arquivos(
    competencia_id: int = Query(...),
    db: Session = Depends(get_db),
) -> list[ArquivoRecebido]:
    return (
        db.query(ArquivoRecebido)
        .filter(ArquivoRecebido.competencia_id == competencia_id)
        .order_by(ArquivoRecebido.created_at.desc())
        .all()
    )


@router.post("", response_model=ArquivoRead, status_code=status.HTTP_201_CREATED)
def enviar_arquivo(
    competencia_id: int = Form(...),
    observacoes: str | None = Form(default=None),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ArquivoRecebido:
    competencia = db.get(Competencia, competencia_id)
    if not competencia:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")
    exigir_competencia_editavel(competencia)

    original = nome_seguro(arquivo.filename or "arquivo")
    extensao = Path(original).suffix.lower()
    if extensao not in EXTENSOES_PERMITIDAS:
        raise HTTPException(status_code=400, detail="Tipo de arquivo não permitido.")

    return salvar_arquivo_original(db,competencia,arquivo,extensoes_esperadas=tuple(EXTENSOES_PERMITIDAS),tipo_arquivo=extensao.lstrip('.'),observacoes=observacoes,uploads_dir=UPLOADS_DIR)


@router.get("/{arquivo_id}/download")
def baixar_arquivo(arquivo_id: int, db: Session = Depends(get_db)) -> FileResponse:
    registro = db.get(ArquivoRecebido, arquivo_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    caminho = Path(registro.caminho_arquivo)
    if not caminho.is_absolute():
        caminho = BACKEND_DIR / caminho
    caminho = caminho.resolve()
    if not caminho.is_relative_to(UPLOADS_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Caminho do arquivo inválido.")
    if not caminho.is_file():
        raise HTTPException(status_code=404, detail="Arquivo físico não encontrado.")

    verificar_hash(caminho,registro.sha256)
    return FileResponse(path=caminho, filename=registro.nome_original,media_type="application/octet-stream",headers={'X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})
