import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from app.database.models import ArquivoRecebido, Competencia
from app.database.session import BACKEND_DIR, UPLOADS_DIR
from hashlib import sha256
from app.database.models import DocumentoEvidencia
from app.importadores.propostas import auditar_arquivo, hash_arquivo

LIMITE_ARQUIVO_BYTES = 25 * 1024 * 1024

def nome_seguro(nome: str) -> str:
    base = Path(nome).name.strip() or "arquivo.xlsx"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base)


def salvar_arquivo_original(
    db: Session,
    competencia: Competencia,
    arquivo: UploadFile,
    *,
    extensoes_esperadas: tuple[str, ...],
    tipo_arquivo: str,
    observacoes: str,
    uploads_dir=UPLOADS_DIR,
) -> ArquivoRecebido:
    original = nome_seguro(arquivo.filename or f"ponto{extensoes_esperadas[0]}")
    extensao = Path(original).suffix.lower()
    if extensao not in extensoes_esperadas:
        raise HTTPException(status_code=400, detail=f"Envie um arquivo {' ou '.join(extensoes_esperadas)}.")

    pasta_destino = uploads_dir / f"empresa_{competencia.empresa_id}" / f"{competencia.ano}-{competencia.mes:02d}"
    try:
        pasta_destino.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Não foi possível preparar o armazenamento do arquivo.") from exc
    nome_final = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}_{original}"
    destino = pasta_destino / nome_final

    try:
        try:
            with destino.open("xb") as buffer:
                total_bytes = 0
                hash = sha256()
                while trecho := arquivo.file.read(1024 * 1024):
                    total_bytes += len(trecho)
                    if total_bytes > LIMITE_ARQUIVO_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail="O arquivo excede o limite de 25 MB.",
                        )
                    buffer.write(trecho)
                    hash.update(trecho)
        finally:
            arquivo.file.close()
    except HTTPException:
        destino.unlink(missing_ok=True)
        raise
    except OSError as exc:
        destino.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Não foi possível salvar o arquivo enviado.") from exc

    try:
        caminho_armazenado = destino.relative_to(BACKEND_DIR).as_posix()
    except ValueError:
        caminho_armazenado = destino.resolve().as_posix()

    if not total_bytes:
        destino.unlink(missing_ok=True)
        raise HTTPException(400, "O arquivo está vazio.")
    digest = hash.hexdigest()
    anteriores = db.query(ArquivoRecebido).filter_by(competencia_id=competencia.id,sha256=digest).all()
    for anterior in anteriores:
        caminho = Path(anterior.caminho_arquivo)
        if not caminho.is_absolute(): caminho = BACKEND_DIR / caminho
        if caminho.resolve().is_relative_to(uploads_dir.resolve()) and caminho.is_file() and hash_arquivo(caminho)==digest:
            destino.unlink(missing_ok=True)
            auditar_arquivo(db, anterior, "reenviado", {"nome":arquivo.filename,"sha256":digest})
            db.commit()
            return anterior

    registro = ArquivoRecebido(
        competencia_id=competencia.id,
        sha256=digest, tamanho_bytes=total_bytes,
        nome_original=arquivo.filename or original,
        caminho_arquivo=caminho_armazenado,
        tipo_arquivo=tipo_arquivo,
        observacoes=observacoes,
    )
    db.add(registro)
    try:
        db.flush()
        db.add(DocumentoEvidencia(arquivo_id=registro.id, caminho_relativo=destino.relative_to(uploads_dir).as_posix(),
            nome_original=registro.nome_original, sha256=digest,tamanho_bytes=total_bytes,origem="upload_original"))
        auditar_arquivo(db, registro, "recebido", {"sha256":digest,"tamanho_bytes":total_bytes})
        db.commit()
    except Exception as exc:
        db.rollback()
        destino.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Não foi possível registrar o arquivo enviado.") from exc
    db.refresh(registro)
    return registro


