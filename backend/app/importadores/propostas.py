"""Propostas preservadas: confirmação não executa parsers."""
import hashlib
import json
from fastapi import HTTPException
from sqlalchemy import inspect
from app.database.models import (Funcionario, Escala, EscalaVersao, HistoricoVinculoEscala,
    IdentificacaoIgnorada, PreviaImportacao, BatidaOriginal, EventoAuditoria, DocumentoEvidencia)

VERSOES_ADAPTADORES = {nome: "1" for nome in (
    "txt_log_relogio", "txt_id_tempo_maquina", "txt_generico", "xlsx_ponto_generico", "xlsx_cartao_ponto")}

def json_estavel(valor):
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

def hash_json(valor):
    return hashlib.sha256(json_estavel(valor).encode()).hexdigest()

def hash_arquivo(caminho):
    hash = hashlib.sha256()
    with caminho.open("rb") as origem:
        for bloco in iter(lambda: origem.read(1024*1024), b""): hash.update(bloco)
    return hash.hexdigest()

def contexto(db, competencia):
    dados = {"motor": 2, "competencia": [competencia.id, competencia.empresa_id, competencia.ano, competencia.mes]}
    for modelo, filtro in (
        (Funcionario, Funcionario.empresa_id == competencia.empresa_id),
        (Escala, Escala.empresa_id == competencia.empresa_id),
        (EscalaVersao, EscalaVersao.escala_id.in_(db.query(Escala.id).filter_by(empresa_id=competencia.empresa_id))),
        (HistoricoVinculoEscala, HistoricoVinculoEscala.funcionario_id.in_(db.query(Funcionario.id).filter_by(empresa_id=competencia.empresa_id))),
        (IdentificacaoIgnorada, IdentificacaoIgnorada.empresa_id == competencia.empresa_id)):
        colunas = [c.key for c in inspect(modelo).columns if c.key not in {"created_at", "updated_at"}]
        dados[modelo.__tablename__] = [[getattr(item,c) for c in colunas] for item in db.query(modelo).filter(filtro).order_by(modelo.id)]
    return hash_json(dados)

def ultima(db, arquivo_id):
    return db.query(PreviaImportacao).filter_by(arquivo_id=arquivo_id).order_by(PreviaImportacao.revisao.desc()).first()

def fonte_bruta(arquivo_id, item):
    pessoa=item["funcionario"]
    return f"arquivo:{arquivo_id}:"+hash_json([pessoa.get("codigo_origem"),pessoa.get("nome_origem"),
        item["data"],item["batidas_originais"],item["origem"].get("linha"),item["origem"].get("coluna"),item["origem"].get("aba")])

def auditar_arquivo(db, arquivo, acao, dados):
    from uuid import uuid4
    db.add(EventoAuditoria(arquivo=arquivo, evento_uid=str(uuid4()), origem="importacao", payload_json=json_estavel({"acao":acao, **dados})))

def preservar(db, competencia, arquivo, proposta, caminho):
    sha = hash_arquivo(caminho)
    if arquivo.sha256 and arquivo.sha256 != sha:
        raise HTTPException(409, "O conteúdo do arquivo original foi alterado; confirmação bloqueada.")
    arquivo.sha256, arquivo.tamanho_bytes = sha, caminho.stat().st_size
    if not db.query(DocumentoEvidencia.id).filter_by(arquivo_id=arquivo.id,sha256=sha).first():
        db.add(DocumentoEvidencia(arquivo_id=arquivo.id,referencia_legada=arquivo.caminho_arquivo,
            nome_original=arquivo.nome_original,sha256=sha,tamanho_bytes=arquivo.tamanho_bytes,origem="hash_observado_legado"))
    anterior = ultima(db, arquivo.id)
    revisao = anterior.revisao+1 if anterior else 1
    proposta["revisao_previa"] = revisao
    proposta["arquivo"]["sha256"] = sha
    adaptador = proposta["tipo_detectado"]
    previa = PreviaImportacao(arquivo_id=arquivo.id, revisao=revisao, arquivo_sha256=sha,
        adaptador=adaptador, adaptador_versao=VERSOES_ADAPTADORES.get(adaptador,"1"),
        contexto_sha256=contexto(db, competencia), proposta_json=json_estavel(proposta))
    db.add(previa)
    existentes = {b.fonte for b in db.query(BatidaOriginal).filter_by(arquivo_id=arquivo.id)}
    for item in proposta["preview"]:
        fonte = fonte_bruta(arquivo.id,item)
        if fonte in existentes: continue
        eventos = item.get("eventos_originais") or [{"valor":v} for v in item["batidas_originais"]]
        for indice, evento in enumerate(eventos):
            valor=evento["valor"]
            db.add(BatidaOriginal(arquivo_id=arquivo.id, fonte=fonte, indice=indice, valor_json=json_estavel(valor),
                origem_json=json_estavel({**item["origem"], **{k:v for k,v in evento.items() if k!="valor"},
                    "registro_id":item["id"], "data":item["data"], "linhas_origem":item.get("linhas_origem"),"indice":indice})))
    auditar_arquivo(db, arquivo, "previa_preservada", {"revisao":revisao, "sha256":sha, "adaptador":adaptador})
    return previa

def carregar_valida(db, competencia, arquivo, caminho, revisao, exigir_revisao):
    previa = ultima(db, arquivo.id)
    if not previa: raise HTTPException(409, "Prévia não preservada. Reanalise o arquivo explicitamente.")
    if exigir_revisao and revisao is None:
        raise HTTPException(409, {"codigo":"revisao_previa_necessaria", "mensagem":"Atualize a prévia antes de confirmar."})
    if revisao is not None and revisao != previa.revisao:
        raise HTTPException(409, {"codigo":"previa_obsoleta", "mensagem":"Existe outra revisão; reanalise a seleção."})
    if (hash_arquivo(caminho) != previa.arquivo_sha256 or contexto(db,competencia) != previa.contexto_sha256
            or VERSOES_ADAPTADORES.get(previa.adaptador,"1") != previa.adaptador_versao):
        raise HTTPException(409, {"codigo":"previa_obsoleta", "mensagem":"Arquivo, cadastro ou regras mudaram. Reanalise explicitamente."})
    return previa, json.loads(previa.proposta_json)
