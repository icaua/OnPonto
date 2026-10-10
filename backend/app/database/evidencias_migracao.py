"""Backfill apenas SQL; nunca abre ou reescreve arquivos da instalação."""
import json
from sqlalchemy import inspect
from app.database.models import (PreviaImportacao,ConfirmacaoImportacaoEvento,DocumentoEvidencia,BatidaOriginal,EventoAuditoria)


def migrar(conexao):
    tabelas=set(inspect(conexao).get_table_names())
    if not {"marcacoes_ponto","arquivos_recebidos"}.issubset(tabelas): return
    colunas={c["name"] for c in inspect(conexao).get_columns("arquivos_recebidos")}
    for campo,tipo in {"sha256":"VARCHAR(64)","tamanho_bytes":"INTEGER"}.items():
        if campo not in colunas: conexao.exec_driver_sql(f"ALTER TABLE arquivos_recebidos ADD COLUMN {campo} {tipo}")
    for modelo in (PreviaImportacao,ConfirmacaoImportacaoEvento,DocumentoEvidencia,BatidaOriginal,EventoAuditoria):
        modelo.__table__.create(conexao,checkfirst=True)
    for entidade,campo_fk in (("marcacoes_ponto","marcacao_id"),("ocorrencias_funcionario","ocorrencia_id")):
        if entidade not in tabelas: continue
        if "historico_json" not in {c["name"] for c in inspect(conexao).get_columns(entidade)}: continue
        for id,historico in conexao.exec_driver_sql(f"""SELECT e.id,e.historico_json FROM {entidade} e
                WHERE e.historico_json IS NOT NULL AND e.historico_json NOT IN ('','[]')
                AND NOT EXISTS (SELECT 1 FROM eventos_auditoria a WHERE a.{campo_fk}=e.id) ORDER BY e.id"""):
            try: eventos=json.loads(historico)
            except (ValueError,TypeError): eventos=[{"json_legado_nao_interpretavel":historico}]
            if not isinstance(eventos,list): eventos=[eventos]
            for indice,evento in enumerate(eventos):
                uid=f"legado:{entidade}:{id}:{indice}"
                conexao.exec_driver_sql(f"""INSERT OR IGNORE INTO eventos_auditoria
                    (evento_uid,{campo_fk},payload_json,origem,created_at) VALUES (?,?,?,'historico_json_legado',CURRENT_TIMESTAMP)""",
                    (uid,id,json.dumps(evento,ensure_ascii=False)))
    for id,arquivo_id,originais in conexao.exec_driver_sql("""SELECT m.id,m.arquivo_origem_id,m.batidas_originais FROM marcacoes_ponto m
            WHERE m.batidas_originais IS NOT NULL AND m.batidas_originais NOT IN ('','[]')
            AND NOT EXISTS (SELECT 1 FROM batidas_originais b WHERE b.marcacao_id=m.id) ORDER BY m.id"""):
        try: valores=json.loads(originais)
        except (ValueError,TypeError): continue  # JSON original permanece intacto; não adivinhar eventos.
        if not isinstance(valores,list): continue
        for indice,valor in enumerate(valores):
            conexao.exec_driver_sql("""INSERT OR IGNORE INTO batidas_originais
                (arquivo_id,marcacao_id,fonte,indice,valor_json,origem_json,created_at) VALUES (?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                (arquivo_id,id,f"json_legado:{id}",indice,json.dumps(valor,ensure_ascii=False),json.dumps({"origem":"json_legado","indice":indice})))
    consulta_arquivos = """SELECT a.id,a.caminho_arquivo,a.nome_original FROM arquivos_recebidos a
            WHERE NOT EXISTS (SELECT 1 FROM documentos_evidencia d WHERE d.arquivo_id=a.id) ORDER BY a.id"""
    arquivos = conexao.exec_driver_sql(consulta_arquivos) if {"caminho_arquivo","nome_original"}.issubset(colunas) else []
    for id,caminho,nome in arquivos:
        conexao.exec_driver_sql("""INSERT INTO documentos_evidencia
            (arquivo_id,referencia_legada,nome_original,origem,created_at) VALUES (?,?,?,'legado_hash_desconhecido',CURRENT_TIMESTAMP)""",(id,caminho,nome))
    if "ocorrencias_funcionario" in tabelas:
        for id,caminho,nome in conexao.exec_driver_sql("""SELECT o.id,o.anexo_caminho,o.anexo_nome FROM ocorrencias_funcionario o
                WHERE o.anexo_caminho IS NOT NULL AND NOT EXISTS (SELECT 1 FROM documentos_evidencia d WHERE d.ocorrencia_id=o.id) ORDER BY o.id"""):
            conexao.exec_driver_sql("""INSERT INTO documentos_evidencia
                (ocorrencia_id,caminho_relativo,nome_original,origem,created_at) VALUES (?,?,?,'legado_hash_desconhecido',CURRENT_TIMESTAMP)""",(id,caminho,nome or "Anexo legado"))
    for tabela in ("previas_importacao","confirmacoes_importacao","documentos_evidencia","eventos_auditoria"):
        for acao in ("UPDATE","DELETE"):
            conexao.exec_driver_sql(f"""CREATE TRIGGER IF NOT EXISTS {tabela}_{acao.lower()} BEFORE {acao} ON {tabela}
                BEGIN SELECT RAISE(ABORT,'Evidencia historica imutavel'); END""")
    conexao.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS batidas_originais_delete BEFORE DELETE ON batidas_originais
        BEGIN SELECT RAISE(ABORT,'Batida original imutavel'); END""")
    campos=("arquivo_id","fonte","indice","valor_json","origem_json","created_at")
    alterados=" OR ".join(f"NEW.{c} IS NOT OLD.{c}" for c in campos)
    conexao.exec_driver_sql(f"""CREATE TRIGGER IF NOT EXISTS batidas_originais_update BEFORE UPDATE ON batidas_originais
        WHEN ({alterados}) OR (OLD.marcacao_id IS NOT NULL AND NEW.marcacao_id IS NOT OLD.marcacao_id)
        BEGIN SELECT RAISE(ABORT,'Batida original imutavel'); END""")
    conexao.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS marcacoes_originais_update BEFORE UPDATE OF batidas_originais ON marcacoes_ponto
        WHEN OLD.batidas_originais IS NOT NULL AND OLD.batidas_originais NOT IN ('','[]')
             AND NEW.batidas_originais IS NOT OLD.batidas_originais
        BEGIN SELECT RAISE(ABORT,'Batidas originais preservadas'); END""")
