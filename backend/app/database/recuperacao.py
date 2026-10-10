"""Conjunto SQLite + arquivos para recuperação offline em diretório novo.

Sem sobrescrita, retenção ou integração automática com dados da instalação.
O chamador deve parar os escritores antes de copiar DB e uploads.
"""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda:file.read(1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()


def verificar_db(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+"?mode=ro",uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchall()!=[("ok",)]:
            raise RuntimeError("Falha de integridade do SQLite.")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("Violação de chave estrangeira no SQLite.")


def inventario(pasta):
    arquivos={}
    for path in sorted(Path(pasta).rglob("*")):
        if path.is_symlink(): raise ValueError("Links não são aceitos no conjunto de recuperação.")
        if path.is_file(): arquivos[path.relative_to(pasta).as_posix()]=sha256(path)
    return arquivos


def criar_conjunto(banco,uploads,destino,*,offline=False):
    if not offline: raise ValueError("Pare a API e os escritores antes do backup do conjunto.")
    banco,uploads,destino=map(lambda p:Path(p).resolve(),(banco,uploads,destino))
    if destino.exists(): raise FileExistsError(destino)
    if destino.is_relative_to(uploads): raise ValueError("Backup deve ficar fora dos uploads.")
    verificar_db(banco)
    antes=inventario(uploads)
    destino.mkdir(parents=True)
    with closing(sqlite3.connect(banco.as_uri()+"?mode=ro",uri=True)) as origem:
        with closing(sqlite3.connect(destino/"onponto.db")) as copia: origem.backup(copia)
    shutil.copytree(uploads,destino/"uploads")
    verificar_db(destino/"onponto.db")
    if antes!=inventario(uploads) or antes!=inventario(destino/"uploads"):
        raise RuntimeError("Arquivos mudaram durante o backup; conjunto não é restaurável.")
    manifest={"versao":1,"banco_sha256":sha256(destino/"onponto.db"),"arquivos":antes}
    (destino/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return manifest


def restaurar_conjunto(origem,destino):
    origem,destino=map(lambda p:Path(p).resolve(),(origem,destino))
    if destino.exists(): raise FileExistsError(destino)
    manifest=json.loads((origem/"manifest.json").read_text(encoding="utf-8"))
    if manifest["versao"]!=1 or sha256(origem/"onponto.db")!=manifest["banco_sha256"]:
        raise RuntimeError("Manifesto ou hash de banco inválido.")
    if inventario(origem/"uploads")!=manifest["arquivos"]:
        raise RuntimeError("Hash de arquivo inválido.")
    verificar_db(origem/"onponto.db")
    shutil.copytree(origem,destino)
    verificar_db(destino/"onponto.db")
    return manifest
