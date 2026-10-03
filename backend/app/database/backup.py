"""Cópias consistentes antes de qualquer escrita do startup."""
from contextlib import closing
from datetime import datetime, timedelta
import logging
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from urllib.parse import unquote, urlsplit

from app.database.migrations import SCHEMA_VERSION
from app.database.session import BACKEND_DIR


logger = logging.getLogger(__name__)


def caminho_banco(engine):
    url = engine.url
    nome = url.database
    if url.get_backend_name() != "sqlite" or not nome or nome == ":memory:" or url.query.get("mode") == "memory":
        return None
    if nome.startswith("file:"):
        if nome == "file::memory:":
            return None
        nome = unquote(urlsplit(nome).path)
        if os.name == "nt" and re.match(r"^/[A-Za-z]:", nome):
            nome = nome[1:]
    return Path(nome).resolve()


def pasta_backups(banco):
    configurada = os.getenv("ONPONTO_BACKUP_DIR")
    if configurada:
        return Path(configurada).resolve()
    if banco == (BACKEND_DIR / "onponto.db").resolve():
        return BACKEND_DIR.parent / "backups" / "automaticos"
    return banco.parent / "backups"


def criar_copia(origem, destino):
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destino.parent, prefix=".backup-", suffix=".tmp", delete=False) as arquivo:
        temporario = Path(arquivo.name)
    try:
        with closing(sqlite3.connect(temporario)) as copia:
            origem.backup(copia)
            if copia.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise RuntimeError("A verificação de integridade da cópia falhou.")
        temporario.replace(destino)
        logger.info("Backup automático criado: %s", destino)
    finally:
        temporario.unlink(missing_ok=True)


def aplicar_retencao(pasta):
    for padrao, limite in (
        (r"onponto-v\d+-antes-da-v\d+-(\d{8}-\d{6})\.db", 10),
        (r"onponto-diario-(\d{8})\.db", 7),
    ):
        arquivos = [(m.group(1), p) for p in pasta.iterdir()
                    if p.is_file() and (m := re.fullmatch(padrao, p.name))]
        for _, arquivo in sorted(arquivos, reverse=True)[limite:]:
            arquivo.unlink()


def realizar_backups_automaticos(engine):
    banco = caminho_banco(engine)
    if banco is None or not banco.exists():
        return
    pasta = pasta_backups(banco)
    agora = datetime.now()
    # Não abrir pelo engine: nem a leitura da versão pode criar ou alterar a origem.
    with closing(sqlite3.connect(banco.as_uri() + "?mode=ro", uri=True)) as origem:
        atual = origem.execute("PRAGMA user_version").fetchone()[0]
        if atual < SCHEMA_VERSION:
            destino = pasta / f"onponto-v{atual}-antes-da-v{SCHEMA_VERSION}-{agora:%Y%m%d-%H%M%S}.db"
            while destino.exists():
                agora += timedelta(seconds=1)
                destino = pasta / f"onponto-v{atual}-antes-da-v{SCHEMA_VERSION}-{agora:%Y%m%d-%H%M%S}.db"
            try:
                criar_copia(origem, destino)
            except Exception as exc:
                raise RuntimeError(f"Não foi possível criar o backup pré-migração em {destino}: {exc}. Inicialização cancelada; o banco não foi migrado.") from exc
        try:
            diario = pasta / f"onponto-diario-{datetime.now():%Y%m%d}.db"
            if not diario.exists():
                criar_copia(origem, diario)
        except Exception:
            logger.warning("Não foi possível criar o backup diário em %s.", pasta, exc_info=True)
    try:
        aplicar_retencao(pasta)
    except OSError:
        logger.warning("Não foi possível aplicar a retenção de backups em %s.", pasta, exc_info=True)
