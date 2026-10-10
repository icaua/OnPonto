import json
import re
import unicodedata
from datetime import date, datetime, time, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Request, APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from openpyxl import load_workbook
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.apuracao.service import placeholder_calendario_intocado
from app.competencias.service import exigir_competencia_editavel
from app.ocorrencias.service import iniciar_escrita
from app.database.transacoes import atomica
from app.database.models import ArquivoRecebido, Competencia, Empresa, Funcionario, IdentificacaoIgnorada, MarcacaoPonto
from app.database.session import BACKEND_DIR, UPLOADS_DIR, get_db
from app.importadores import ignorados, armazenamento, pipeline, propostas
from app.importadores.schemas import ConfirmacaoImportacao, IdentificacaoIgnoradaCreate
from app.database.models import PreviaImportacao, ConfirmacaoImportacaoEvento, BatidaOriginal

router = APIRouter(prefix="/importadores", tags=["Importadores"])
LIMITE_ARQUIVO_BYTES = armazenamento.LIMITE_ARQUIVO_BYTES
EXTENSOES_SUPORTADAS = pipeline.EXTENSOES_SUPORTADAS
NOMES_ADAPTADORES = pipeline.NOMES_ADAPTADORES
FUNCOES_PARSE = pipeline.FUNCOES_PARSE


def salvar_arquivo_original(db, competencia, arquivo, **kwargs):
    return armazenamento.salvar_arquivo_original(db, competencia, arquivo, uploads_dir=UPLOADS_DIR, **kwargs)

def caminho_arquivo_recebido(registro):
    return pipeline.caminho_arquivo_recebido(registro, UPLOADS_DIR)

def gerar_previa(db, competencia, registro):
    return pipeline.gerar_previa(db, competencia, registro, UPLOADS_DIR)

def validar_contexto_importacao(db: Session, empresa_id: int, competencia_id: int) -> tuple[Empresa, Competencia]:
    empresa = db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")

    competencia = db.get(Competencia, competencia_id)
    if not competencia:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")
    if competencia.empresa_id != empresa.id:
        raise HTTPException(status_code=400, detail="Competência não pertence à empresa informada.")
    exigir_competencia_editavel(competencia)
    return empresa, competencia


def analisar_arquivo_salvo(db: Session, competencia: Competencia, registro: ArquivoRecebido, *, commit=True) -> dict:
    hash_antes = propostas.hash_arquivo(caminho_arquivo_recebido(registro))
    adaptador, resultado = gerar_previa(db, competencia, registro)
    if propostas.hash_arquivo(caminho_arquivo_recebido(registro)) != hash_antes:
        raise HTTPException(409, "O arquivo mudou durante a análise. Nenhuma proposta foi confirmada.")
    preview = resultado["registros"]
    confirmacoes_anteriores = (registro.observacoes or "").partition(" Confirmação:")[2]
    registro.tipo_arquivo = adaptador.NOME_ADAPTER
    registro.observacoes = (
        f"Arquivo original preservado. Formato: {adaptador.NOME_ADAPTER}; "
        f"encoding: {resultado.get('encoding') or 'não se aplica'}; "
        f"linhas válidas: {resultado['total_linhas_validas']}; "
        f"linhas rejeitadas/não interpretadas: {resultado.get('total_linhas_ignoradas', 0)}; "
        f"dias identificados: {len(preview)}; "
        f"dias para conferência: {sum(bool(item['pendencias']) for item in preview)}."
    )
    if confirmacoes_anteriores:
        registro.observacoes += " Confirmação:" + confirmacoes_anteriores
    controle = json.loads(registro.controle_importacao_json) if registro.controle_importacao_json else {}
    ignorados.aplicar_regras(controle, preview, ignorados.regras_ativas(db, competencia.empresa_id))
    resolvidos = set(controle.get("importados", [])) | {p["registro_id"] for p in controle.get("descartados", [])}
    pendencias = [ignorados.pendencia_do_registro(p) for p in preview if p["id"] not in resolvidos]
    # Sem registro pendente não há o que confirmar (ex.: arquivo só com pessoas ignoradas).
    controle.update(estado="analisada" if pendencias else "confirmada", pendencias=pendencias)
    registro.controle_importacao_json = json.dumps(controle, ensure_ascii=False)
    for item in preview:
        item["origem"]["arquivo_id"] = registro.id
        if item["id"] in resolvidos:
            item["selecionado"] = False
            item["ja_resolvido"] = True

    funcionarios_encontrados = {
        item["funcionario"]["id"] for item in preview if item["funcionario"]["encontrado"]
    }
    funcionarios_nao_encontrados = {
        (item["funcionario"]["codigo_origem"], item["funcionario"]["nome_origem"])
        for item in preview
        if not item["funcionario"]["encontrado"] and not item.get("ignorado")
    }
    pessoas_ignoradas = {
        (item["funcionario"]["codigo_origem"], item["funcionario"]["nome_origem"])
        for item in preview
        if item.get("ignorado")
    }
    proposta = {
        "arquivo": {
            "id": registro.id,
            "nome_original": registro.nome_original,
            "tipo_arquivo": registro.tipo_arquivo,
        },
        "tipo_detectado": adaptador.NOME_ADAPTER,
        "encoding": resultado.get("encoding"),
        "empresa_id": competencia.empresa_id,
        "competencia_id": competencia.id,
        "total_linhas_validas": resultado["total_linhas_validas"],
        "total_linhas_ignoradas": resultado.get("total_linhas_ignoradas", 0),
        "avisos_importacao": resultado.get("avisos", []),
        "linhas_rejeitadas": resultado.get("linhas_rejeitadas", []),
        "total_funcionarios_encontrados": len(funcionarios_encontrados),
        "total_funcionarios_nao_cadastrados": len(funcionarios_nao_encontrados),
        "total_pessoas_ignoradas": len(pessoas_ignoradas),
        "total_registros_ignorados": sum(1 for item in preview if item.get("ignorado")),
        "total_batidas": sum(len(item["batidas_originais"]) for item in preview),
        "total_dias": len(preview),
        "total_pendencias": sum(len(item["pendencias"]) for item in preview),
        "total_registros_com_pendencia": sum(1 for item in preview if item["pendencias"]),
        "registros_fora_competencia": sum(1 for item in preview if item["fora_da_competencia"]),
        "preview": preview,
    }
    propostas.preservar(db, competencia, registro, proposta, caminho_arquivo_recebido(registro))
    from app.competencias.service import sincronizar_status_competencia
    sincronizar_status_competencia(db, competencia)
    if commit: db.commit()
    else: db.flush()
    return proposta



def hora_interpretada(valor: str | None) -> time | None:
    return time.fromisoformat(valor) if valor else None


@router.post("/{arquivo_id}/reanalisar")
@atomica
def reanalisar(arquivo_id: int, db: Session = Depends(get_db)):
    arquivo = db.get(ArquivoRecebido, arquivo_id)
    if not arquivo:
        raise HTTPException(404, "Arquivo não encontrado.")
    competencia = db.get(Competencia, arquivo.competencia_id)
    exigir_competencia_editavel(competencia)
    return analisar_arquivo_salvo(db, competencia, arquivo)


from app.importadores.schemas import DescartePendencias


@router.post("/{arquivo_id}/descartar-pendencias")
@atomica
def descartar_pendencias(arquivo_id: int, payload: DescartePendencias, db: Session = Depends(get_db)):
    """Exclusão justificada de registros da apuração; preserva arquivo e trilha."""
    arquivo = db.get(ArquivoRecebido, arquivo_id)
    if not arquivo:
        raise HTTPException(404, "Arquivo não encontrado.")
    exigir_competencia_editavel(db.get(Competencia, arquivo.competencia_id))
    controle = json.loads(arquivo.controle_importacao_json or "{}")
    pendencias = controle.get("pendencias", [])
    ids = set(payload.registros_ids)
    if not ids.issubset({p["registro_id"] for p in pendencias}):
        raise HTTPException(422, "Seleção não corresponde às pendências do arquivo.")
    if len(payload.justificativa.strip()) < 10:
        raise HTTPException(422, "Informe uma justificativa com ao menos dez caracteres.")
    controle.setdefault("descartados", []).extend({**p, "justificativa": payload.justificativa.strip(),
        "em": datetime.now(timezone.utc).isoformat()} for p in pendencias if p["registro_id"] in ids)
    controle["pendencias"] = [p for p in pendencias if p["registro_id"] not in ids]
    controle["estado"] = "confirmada"
    arquivo.controle_importacao_json = json.dumps(controle, ensure_ascii=False)
    propostas.auditar_arquivo(db, arquivo, "descarte_justificado", {"ids":sorted(ids),"justificativa":payload.justificativa.strip()})
    from app.competencias.service import sincronizar_status_competencia
    sincronizar_status_competencia(db, arquivo.competencia)
    db.commit()
    return {"descartados": len(ids), "restantes": len(controle["pendencias"])}


@router.get("/{arquivo_id}/pendencias-agrupadas")
def pendencias_agrupadas(arquivo_id: int, db: Session = Depends(get_db)):
    """Agrupa as pendências por pessoa do relógio, sem gravar nada."""
    arquivo = db.get(ArquivoRecebido, arquivo_id)
    if not arquivo:
        raise HTTPException(404, "Arquivo não encontrado.")
    pendencias = (arquivo.controle_importacao or {}).get("pendencias", [])
    identidades = {}
    if any("nome_origem" not in p for p in pendencias):
        # Arquivos analisados antes desta versão não guardavam a identidade na pendência.
        _, resultado = gerar_previa(db, arquivo.competencia, arquivo)
        identidades = {item["id"]: ignorados.pendencia_do_registro(item) for item in resultado["registros"]}
    grupos = {}
    for pendencia in pendencias:
        completa = {**identidades.get(pendencia["registro_id"], {}), **pendencia}
        chave = (ignorados.normalizar_codigo(completa.get("codigo_origem")), ignorados.normalizar_nome(completa.get("nome_origem")))
        grupo = grupos.setdefault(chave, {"codigo_origem": completa.get("codigo_origem"), "nome_origem": completa.get("nome_origem"),
                                         "funcionario_encontrado": completa.get("funcionario_encontrado", True), "registros": []})
        grupo["registros"].append({k: completa.get(k) for k in ("registro_id", "data", "mensagem", "tipo")})
    return sorted(grupos.values(), key=lambda g: (g["funcionario_encontrado"], ignorados.normalizar_nome(g["nome_origem"]),
                                                  ignorados.normalizar_codigo(g["codigo_origem"])))


@router.get("/ignorados")
def listar_ignorados(empresa_id: int, incluir_inativas: bool = False, db: Session = Depends(get_db)):
    query = db.query(IdentificacaoIgnorada).filter_by(empresa_id=empresa_id)
    if not incluir_inativas:
        query = query.filter_by(ativa=True)
    return [ignorados.serializar(regra) for regra in query.order_by(IdentificacaoIgnorada.id)]


def arquivos_editaveis(db: Session, empresa_id: int) -> list[ArquivoRecebido]:
    return (db.query(ArquivoRecebido).join(Competencia)
            .filter(Competencia.empresa_id == empresa_id, Competencia.status != "fechada",
                    ArquivoRecebido.controle_importacao_json.isnot(None))
            .order_by(ArquivoRecebido.id).all())


@router.post("/ignorados", status_code=status.HTTP_201_CREATED)
@atomica
def ignorar_identificacao(payload: IdentificacaoIgnoradaCreate, db: Session = Depends(get_db)):
    """Ignora uma pessoa do relógio nesta empresa e aplica a decisão às competências abertas."""
    iniciar_escrita(db)
    if not db.get(Empresa, payload.empresa_id):
        raise HTTPException(404, "Empresa não encontrada.")
    regra = IdentificacaoIgnorada(**payload.model_dump())
    for funcionario in db.query(Funcionario).filter_by(empresa_id=payload.empresa_id):
        if ignorados.corresponde(regra, funcionario.codigo, funcionario.nome):
            raise HTTPException(409, f"{funcionario.nome_apresentacao} está cadastrado no OnPonto com esta identificação; o cadastro prevalece.")
    if any(ignorados.corresponde(r, regra.codigo_origem, regra.nome_origem) for r in ignorados.regras_ativas(db, payload.empresa_id)):
        raise HTTPException(409, "Esta pessoa já está ignorada nas importações desta empresa.")
    db.add(regra)
    db.flush()
    excluidos, falhas = 0, []
    for arquivo in arquivos_editaveis(db, payload.empresa_id):
        try:
            _, resultado = gerar_previa(db, arquivo.competencia, arquivo)
        except HTTPException as exc:
            falhas.append({"arquivo_id": arquivo.id, "motivo": exc.detail})
            continue
        controle = arquivo.controle_importacao
        novos = ignorados.aplicar_regras(controle, resultado["registros"], [regra])
        if novos:
            if not controle["pendencias"]:
                controle["estado"] = "confirmada"
            arquivo.controle_importacao_json = json.dumps(controle, ensure_ascii=False)
            excluidos += novos
    for arquivo in arquivos_editaveis(db, payload.empresa_id):
        propostas.auditar_arquivo(db,arquivo,"identificacao_ignorada",ignorados.serializar(regra))
    sincronizar_empresa(db,payload.empresa_id)
    db.commit()
    db.refresh(regra)
    return {"regra": ignorados.serializar(regra), "registros_excluidos": excluidos, "arquivos_nao_reprocessados": falhas}


@router.delete("/ignorados/{regra_id}")
@atomica
def deixar_de_ignorar(regra_id: int, db: Session = Depends(get_db)):
    """Desativa a regra; registros excluídos por ela em competências abertas voltam a pendências."""
    iniciar_escrita(db)
    regra = db.get(IdentificacaoIgnorada, regra_id)
    if not regra or not regra.ativa:
        raise HTTPException(404, "Regra não encontrada ou já desativada.")
    regra.ativa = False
    regra.desativada_em = datetime.now(timezone.utc).replace(tzinfo=None)
    restaurados = 0
    for arquivo in arquivos_editaveis(db, regra.empresa_id):
        controle = arquivo.controle_importacao
        quantidade = ignorados.restaurar_regra(controle, regra.id)
        if quantidade:
            arquivo.controle_importacao_json = json.dumps(controle, ensure_ascii=False)
            restaurados += quantidade
    for arquivo in arquivos_editaveis(db, regra.empresa_id):
        propostas.auditar_arquivo(db,arquivo,"identificacao_restaurada",ignorados.serializar(regra))
    sincronizar_empresa(db,regra.empresa_id)
    db.commit()
    return {"regra": ignorados.serializar(regra), "registros_restaurados": restaurados}


def placeholder_calendario_vazio(marcacao: MarcacaoPonto) -> bool:
    return placeholder_calendario_intocado(marcacao)


@router.post("/analisar", status_code=status.HTTP_201_CREATED)
def analisar_importacao(
    competencia_id: int = Form(...),
    empresa_id: int = Form(...),
    mes: int = Form(...),
    ano: int = Form(...),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    iniciar_escrita(db)
    _, competencia = validar_contexto_importacao(db, empresa_id, competencia_id)
    if competencia.mes != mes or competencia.ano != ano:
        raise HTTPException(status_code=400, detail="Mês/ano não correspondem à competência informada.")

    extensao = Path(arquivo.filename or "").suffix.lower()
    if extensao not in EXTENSOES_SUPORTADAS:
        raise HTTPException(status_code=400, detail="Envie um arquivo .txt ou .xlsx.")

    registro = salvar_arquivo_original(
        db,
        competencia,
        arquivo,
        extensoes_esperadas=EXTENSOES_SUPORTADAS,
        tipo_arquivo="txt" if extensao == ".txt" else "xlsx",
        observacoes="Arquivo original preservado para análise de importação de ponto.",
    )
    try:
        # O original já está preservado; a análise revalida sob novo lock.
        iniciar_escrita(db)
        db.refresh(competencia)
        exigir_competencia_editavel(competencia)
        return analisar_arquivo_salvo(db, competencia, registro)
    except HTTPException as exc:
        db.rollback()
        registro.observacoes = f"Falha na análise do arquivo: {exc.detail}"
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
        raise


@router.post("/confirmar", status_code=status.HTTP_201_CREATED)
@atomica
def confirmar_importacao(
    payload: ConfirmacaoImportacao,
    db: Session = Depends(get_db),
    request: Request = None,
) -> dict:
    _, competencia = validar_contexto_importacao(db, payload.empresa_id, payload.competencia_id)
    if not payload.registros_ids:
        raise HTTPException(status_code=400, detail="Selecione ao menos um registro para importar.")

    arquivo = db.get(ArquivoRecebido, payload.arquivo_id)
    if not arquivo:
        raise HTTPException(status_code=404, detail="Arquivo de importação não encontrado.")
    if arquivo.competencia_id != competencia.id:
        raise HTTPException(status_code=400, detail="Arquivo não pertence à competência informada.")
    if arquivo.tipo_arquivo not in NOMES_ADAPTADORES:
        raise HTTPException(
            status_code=400,
            detail="Arquivo informado ainda não foi analisado por um adaptador reconhecido.",
        )

    db.refresh(competencia)
    exigir_competencia_editavel(competencia)
    previa, analise = propostas.carregar_valida(db, competencia, arquivo, caminho_arquivo_recebido(arquivo),
        payload.revisao_previa, request is not None)
    chave = propostas.hash_json([previa.id, sorted(set(payload.registros_ids))])
    confirmacao = db.query(ConfirmacaoImportacaoEvento).filter_by(chave=chave).first()
    if confirmacao: return {**json.loads(confirmacao.resposta_json), "idempotente":True}
    registros_por_id = {item["id"]: item for item in analise["preview"]}
    ids_selecionados = list(dict.fromkeys(payload.registros_ids))
    ids_invalidos = [registro_id for registro_id in ids_selecionados if registro_id not in registros_por_id]
    if ids_invalidos:
        raise HTTPException(status_code=400, detail="A seleção não corresponde à prévia atual do arquivo.")

    conflitos: list[dict] = []
    marcacoes: list[MarcacaoPonto] = []
    chaves_reservadas: set[tuple[int, date]] = set()
    funcionarios = {f.id:f for f in db.query(Funcionario).filter_by(empresa_id=competencia.empresa_id)}
    existentes = {(m.funcionario_id,m.data):m for m in db.query(MarcacaoPonto).filter_by(competencia_id=competencia.id)}
    brutas = {}
    for batida in db.query(BatidaOriginal).filter_by(arquivo_id=arquivo.id): brutas.setdefault(batida.fonte,[]).append(batida)
    controle = arquivo.controle_importacao or {}
    resolvidos = set(controle.get("importados",[])) | {p["registro_id"] for p in controle.get("descartados",[])}
    for registro_id in ids_selecionados:
        if registro_id in resolvidos: continue
        item = registros_por_id[registro_id]
        funcionario_info = item["funcionario"]
        funcionario = funcionarios.get(funcionario_info["id"]) if funcionario_info["id"] else None
        if not funcionario or funcionario.empresa_id != payload.empresa_id:
            conflitos.append(
                {
                    "registro_id": registro_id,
                    "tipo": "funcionario_nao_encontrado",
                    "funcionario": funcionario_info["nome_origem"],
                    "data": item["data"],
                    "mensagem": "Funcionário não cadastrado para esta empresa.",
                }
            )
            continue

        if item["fora_da_competencia"]:
            conflitos.append(
                {
                    "registro_id": registro_id,
                    "tipo": "data_fora_competencia",
                    "funcionario": funcionario.nome,
                    "data": item["data"],
                    "mensagem": "A data do registro está fora da competência selecionada.",
                }
            )
            continue

        data_marcacao = date.fromisoformat(item["data"])
        chave_marcacao = (funcionario.id, data_marcacao)
        if chave_marcacao in chaves_reservadas:
            conflitos.append(
                {
                    "registro_id": registro_id,
                    "tipo": "marcacao_duplicada",
                    "funcionario": funcionario.nome,
                    "data": item["data"],
                    "mensagem": "Já existe uma marcação para este funcionário nesta data.",
                }
            )
            continue
        existente = existentes.get(chave_marcacao)
        if existente and not placeholder_calendario_vazio(existente):
            conflitos.append(
                {
                    "registro_id": registro_id,
                    "tipo": "marcacao_duplicada",
                    "funcionario": funcionario.nome,
                    "data": item["data"],
                    "mensagem": "Já existe uma marcação para este funcionário nesta data.",
                }
            )
            continue

        interpretacao = item["interpretacao"]
        marcacao = existente or MarcacaoPonto(
            competencia_id=competencia.id,
            funcionario_id=funcionario.id,
            data=data_marcacao,
        )
        marcacao.entrada = hora_interpretada(interpretacao.get("entrada"))
        marcacao.saida_almoco = hora_interpretada(interpretacao.get("saida_intervalo"))
        marcacao.retorno_almoco = hora_interpretada(interpretacao.get("retorno_intervalo"))
        marcacao.saida = hora_interpretada(interpretacao.get("saida"))
        marcacao.status_dia = "normal"
        marcacao.origem = arquivo.tipo_arquivo
        marcacao.conferido = False
        marcacao.observacoes = "; ".join(item["pendencias"]) or None
        marcacao.batidas_originais = json.dumps(item["batidas_originais"], ensure_ascii=False)
        marcacao.arquivo_origem_id = arquivo.id
        chaves_reservadas.add(chave_marcacao)
        db.add(marcacao)
        marcacoes.append(marcacao)
        db.flush()
        for batida in brutas.get(propostas.fonte_bruta(arquivo.id,item), []):
            if batida.marcacao_id is None: batida.marcacao_id = marcacao.id
        from app.marcacoes.auditoria import registrar_alteracao
        registrar_alteracao(marcacao, None)

    arquivo.observacoes = (arquivo.observacoes or "") + (
        f" Confirmação: {datetime.now(timezone.utc).isoformat()}; {len(ids_selecionados)} dias solicitados; "
        f"{len(marcacoes)} importados; {len(conflitos)} conflitos."
    )
    controle = json.loads(arquivo.controle_importacao_json)
    importados = set(controle.get("importados", [])) | (set(ids_selecionados) - {c["registro_id"] for c in conflitos})
    controle["importados"] = sorted(importados)
    conflitos_por_id = {c["registro_id"]: c for c in conflitos}
    # O conflito substitui a mensagem, mas a identidade do relógio continua na pendência.
    controle["pendencias"] = [{**p, **conflitos_por_id.get(p["registro_id"], {})} for p in controle["pendencias"] if p["registro_id"] not in importados]
    controle["estado"] = "confirmada"
    arquivo.controle_importacao_json = json.dumps(controle, ensure_ascii=False)
    if marcacoes:
        from app.apuracao.service import gerar_dias_faltantes
        gerar_dias_faltantes(db, competencia)
    from app.competencias.service import sincronizar_status_competencia
    sincronizar_status_competencia(db, competencia)
    resposta = {
        "arquivo_id": arquivo.id, "competencia_id": competencia.id, "revisao_previa":previa.revisao,
        "total_solicitados":len(ids_selecionados), "total_importados":len(marcacoes),
        "marcacoes_ids":[m.id for m in marcacoes], "total_conflitos":len(conflitos), "conflitos":conflitos,
    }
    db.add(ConfirmacaoImportacaoEvento(previa_id=previa.id,chave=chave,selecao_json=propostas.json_estavel(ids_selecionados),
        resposta_json=propostas.json_estavel(resposta)))
    propostas.auditar_arquivo(db,arquivo,"confirmacao",resposta)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        raise HTTPException(500, "Não foi possível salvar a importação; a transação foi revertida.") from exc
    return resposta

@router.get("/{arquivo_id}/previa")
def consultar_previa(arquivo_id:int, db:Session=Depends(get_db)):
    previa=propostas.ultima(db,arquivo_id)
    if not previa: raise HTTPException(404,"Prévia não encontrada. Reanalise o arquivo.")
    return json.loads(previa.proposta_json)

def sincronizar_empresa(db, empresa_id):
    from app.competencias.service import sincronizar_status_competencia
    for competencia in db.query(Competencia).filter(Competencia.empresa_id==empresa_id,Competencia.status!="fechada"):
        sincronizar_status_competencia(db,competencia)
