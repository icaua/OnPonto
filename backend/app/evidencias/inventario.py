"""Inventário somente leitura; não corrige referências nem exclui órfãos."""
from pathlib import Path
from app.database.models import ArquivoRecebido, DocumentoEvidencia, OcorrenciaFuncionario
from app.importadores.propostas import hash_arquivo

def verificar(db, uploads_dir, backend_dir):
    raiz=Path(uploads_dir).resolve()
    referencias={}
    def adicionar(caminho, sha, identificacao):
        caminho=Path(caminho).resolve()
        if not caminho.is_relative_to(raiz):
            invalidas.append(identificacao); return
        referencias.setdefault(caminho,[]).append((sha,identificacao))
    invalidas=[]
    for arquivo in db.query(ArquivoRecebido):
        caminho=Path(arquivo.caminho_arquivo)
        adicionar(caminho if caminho.is_absolute() else Path(backend_dir)/caminho,arquivo.sha256,{"arquivo_id":arquivo.id})
    for doc in db.query(DocumentoEvidencia):
        if doc.caminho_relativo: adicionar(raiz/doc.caminho_relativo,doc.sha256,{"documento_id":doc.id})
        elif doc.referencia_legada:
            caminho=Path(doc.referencia_legada)
            adicionar(caminho if caminho.is_absolute() else Path(backend_dir)/caminho,doc.sha256,{"documento_id":doc.id})
    for ocorrencia in db.query(OcorrenciaFuncionario):
        if ocorrencia.anexo_caminho: adicionar(raiz/ocorrencia.anexo_caminho,None,{"ocorrencia_id":ocorrencia.id})
    ausentes=[]; alteradas=[]; desconhecidas=[]
    for caminho, itens in referencias.items():
        if not caminho.is_file(): ausentes.extend(i for _,i in itens); continue
        hash = hash_arquivo(caminho)
        alteradas.extend(i for sha,i in itens if sha and sha!=hash)
        desconhecidas.extend(i for sha,i in itens if not sha)
    orfaos=[p.relative_to(raiz).as_posix() for p in sorted(raiz.rglob("*")) if p.is_file() and p.resolve() not in referencias]
    return {"ausentes":ausentes,"hash_divergente":alteradas,"hash_desconhecido":desconhecidas,"referencias_invalidas":invalidas,"orfaos":orfaos}

if __name__=="__main__":
    import argparse, json
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    parser=argparse.ArgumentParser(description="Inspeção somente leitura; nenhuma exclusão de arquivo.")
    parser.add_argument("--banco",type=Path,required=True)
    parser.add_argument("--uploads",type=Path,required=True)
    parser.add_argument("--backend",type=Path,required=True)
    args=parser.parse_args()
    if not args.banco.is_file(): parser.error("Banco não encontrado.")
    engine=create_engine(f"sqlite:///file:{args.banco.resolve().as_posix()}?mode=ro&uri=true")
    try:
        with Session(engine) as db: print(json.dumps(verificar(db,args.uploads,args.backend),ensure_ascii=False,indent=2))
    finally: engine.dispose()
