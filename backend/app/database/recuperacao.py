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
from app.evidencias.caminhos import resolver_referencia


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


def referencias_db(banco,uploads,backend):
    referencias={}
    with closing(sqlite3.connect(Path(banco).resolve().as_uri()+"?mode=ro",uri=True)) as db:
        tabelas={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        def incluir(valor,esperado=None,relativo=False):
            if not valor:return
            caminho=(uploads/valor).resolve() if relativo else resolver_referencia(valor,uploads,backend)
            if not caminho.is_relative_to(uploads) or not caminho.is_file():
                raise RuntimeError('Referência de arquivo ausente ou inválida; backup interrompido.')
            if esperado and sha256(caminho)!=esperado:raise RuntimeError('Hash de evidência divergente; backup interrompido.')
            referencias[str(valor)]=caminho.relative_to(uploads).as_posix()
        if 'arquivos_recebidos' in tabelas:
            colunas={r[1] for r in db.execute('PRAGMA table_info(arquivos_recebidos)')}
            for valor,hash in db.execute('SELECT caminho_arquivo,'+('sha256' if 'sha256' in colunas else 'NULL')+' FROM arquivos_recebidos'):
                incluir(valor,hash)
        if 'documentos_evidencia' in tabelas:
            for relativo,legado,hash in db.execute('SELECT caminho_relativo,referencia_legada,sha256 FROM documentos_evidencia'):
                incluir(relativo or legado,hash,relativo=bool(relativo))
        if 'ocorrencias_funcionario' in tabelas:
            colunas={r[1] for r in db.execute('PRAGMA table_info(ocorrencias_funcionario)')}
            if 'anexo_caminho' in colunas:
                for valor, in db.execute('SELECT anexo_caminho FROM ocorrencias_funcionario'):incluir(valor,relativo=True)
    return referencias

def criar_conjunto(banco,uploads,destino,*,offline=False,backend=None):
    if not offline: raise ValueError("Pare a API e os escritores antes do backup do conjunto.")
    banco,uploads,destino=map(lambda p:Path(p).resolve(),(banco,uploads,destino))
    if destino.exists(): raise FileExistsError(destino)
    if destino.is_relative_to(uploads): raise ValueError("Backup deve ficar fora dos uploads.")
    verificar_db(banco)
    referencias=referencias_db(banco,uploads,Path(backend).resolve() if backend else uploads.parent)
    antes=inventario(uploads)
    destino.mkdir(parents=True)
    with closing(sqlite3.connect(banco.as_uri()+"?mode=ro",uri=True)) as origem:
        with closing(sqlite3.connect(destino/"onponto.db")) as copia: origem.backup(copia)
    shutil.copytree(uploads,destino/"uploads")
    verificar_db(destino/"onponto.db")
    if antes!=inventario(uploads) or antes!=inventario(destino/"uploads"):
        raise RuntimeError("Arquivos mudaram durante o backup; conjunto não é restaurável.")
    manifest={"versao":2,"banco_sha256":sha256(destino/"onponto.db"),"arquivos":antes,"referencias":referencias}
    (destino/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return manifest


def restaurar_conjunto(origem,destino):
    origem,destino=map(lambda p:Path(p).resolve(),(origem,destino))
    if destino.exists(): raise FileExistsError(destino)
    manifest=json.loads((origem/"manifest.json").read_text(encoding="utf-8"))
    if manifest["versao"] not in (1,2) or sha256(origem/"onponto.db")!=manifest["banco_sha256"]:
        raise RuntimeError("Manifesto ou hash de banco inválido.")
    if inventario(origem/"uploads")!=manifest["arquivos"]:
        raise RuntimeError("Hash de arquivo inválido.")
    verificar_db(origem/"onponto.db")
    for relativo in manifest.get('referencias',{}).values():
        if not isinstance(relativo,str) or not (origem/'uploads'/relativo).resolve().is_relative_to((origem/'uploads').resolve()) or relativo not in manifest['arquivos']:
            raise RuntimeError('Mapeamento de referência inválido.')
    # Reserva exclusiva: a limpeza só pode atingir o diretório novo desta chamada.
    # Um destino preexistente (inclusive criado após a validação) nunca entra no try.
    destino.mkdir(parents=True)
    try:
        shutil.copytree(origem,destino,dirs_exist_ok=True)
        if manifest['versao']==2:
            with closing(sqlite3.connect(destino/'onponto.db')) as db:
                if db.execute("SELECT 1 FROM sqlite_master WHERE name='arquivos_recebidos'").fetchone():
                    for id,referencia in db.execute('SELECT id,caminho_arquivo FROM arquivos_recebidos').fetchall():
                        relativo=manifest['referencias'].get(referencia)
                        if relativo is None:raise RuntimeError('Referência sem mapeamento; restauração não concluída.')
                        db.execute('UPDATE arquivos_recebidos SET caminho_arquivo=? WHERE id=?',((destino/'uploads'/relativo).as_posix(),id))
                    db.commit()
            (destino/'restauracao.json').write_text(json.dumps({'versao':1,'referencias':manifest['referencias'],'banco_origem_sha256':manifest['banco_sha256'],'banco_restaurado_sha256':sha256(destino/'onponto.db')},ensure_ascii=False,indent=2),encoding='utf-8')
        verificar_db(destino/"onponto.db")
    except Exception:
        shutil.rmtree(destino)
        raise
    return manifest

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Backup/restore offline em destino novo; nunca sobrescreve instalação.')
    comandos=parser.add_subparsers(dest='comando',required=True)
    backup=comandos.add_parser('backup');backup.add_argument('--banco',required=True);backup.add_argument('--uploads',required=True);backup.add_argument('--backend');backup.add_argument('--destino',required=True);backup.add_argument('--offline',action='store_true',required=True)
    restore=comandos.add_parser('restore');restore.add_argument('--origem',required=True);restore.add_argument('--destino',required=True)
    args=parser.parse_args()
    if args.comando=='backup':criar_conjunto(args.banco,args.uploads,args.destino,offline=args.offline,backend=args.backend)
    else:restaurar_conjunto(args.origem,args.destino)
    print('Conjunto verificado; nenhuma origem sobrescrita.')
