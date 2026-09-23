import json
import re
import unicodedata
from datetime import date, datetime, time, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from openpyxl import load_workbook
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.apuracao.service import placeholder_calendario_intocado
from app.competencias.service import exigir_competencia_editavel
from app.database.models import ArquivoRecebido, Competencia, Empresa, Funcionario, MarcacaoPonto
from app.database.session import BACKEND_DIR, UPLOADS_DIR, get_db
from app.importadores.deteccao import (
    ADAPTADORES_TXT,
    ADAPTADORES_XLSX,
    detectar_adaptadores_txt,
    detectar_adaptadores_xlsx,
)
from app.importadores.schemas import ConfirmacaoImportacao
from app.importadores.txt_generico import parse_txt_generico
from app.importadores.txt_id_tempo_maquina import parse_txt_id_tempo_maquina
from app.importadores.txt_log_relogio import parse_txt_log_relogio
from app.importadores.xlsx_cartao_ponto import parse_xlsx_cartao_ponto
from app.importadores.xlsx_ponto_generico import parse_xlsx_ponto_generico


router = APIRouter(prefix="/importadores", tags=["Importadores"])
LIMITE_ARQUIVO_BYTES = 25 * 1024 * 1024

EXTENSOES_SUPORTADAS = (".txt", ".xlsx")
NOMES_ADAPTADORES = {adaptador.NOME_ADAPTER for adaptador in (*ADAPTADORES_TXT, *ADAPTADORES_XLSX)}
FUNCOES_PARSE = {
    "txt_log_relogio": parse_txt_log_relogio,
    "txt_id_tempo_maquina": parse_txt_id_tempo_maquina,
    "txt_generico": parse_txt_generico,
    ADAPTADORES_XLSX[0].NOME_ADAPTER: parse_xlsx_ponto_generico,
    ADAPTADORES_XLSX[1].NOME_ADAPTER: parse_xlsx_cartao_ponto,
}


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
) -> ArquivoRecebido:
    original = nome_seguro(arquivo.filename or f"ponto{extensoes_esperadas[0]}")
    extensao = Path(original).suffix.lower()
    if extensao not in extensoes_esperadas:
        raise HTTPException(status_code=400, detail=f"Envie um arquivo {' ou '.join(extensoes_esperadas)}.")

    pasta_destino = UPLOADS_DIR / f"empresa_{competencia.empresa_id}" / f"{competencia.ano}-{competencia.mes:02d}"
    try:
        pasta_destino.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Não foi possível preparar o armazenamento do arquivo.") from exc
    nome_final = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}_{original}"
    destino = pasta_destino / nome_final

    try:
        try:
            with destino.open("wb") as buffer:
                total_bytes = 0
                while trecho := arquivo.file.read(1024 * 1024):
                    total_bytes += len(trecho)
                    if total_bytes > LIMITE_ARQUIVO_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail="O arquivo excede o limite de 25 MB.",
                        )
                    buffer.write(trecho)
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

    registro = ArquivoRecebido(
        competencia_id=competencia.id,
        nome_original=arquivo.filename or original,
        caminho_arquivo=caminho_armazenado,
        tipo_arquivo=tipo_arquivo,
        observacoes=observacoes,
    )
    db.add(registro)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        destino.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Não foi possível registrar o arquivo enviado.") from exc
    db.refresh(registro)
    return registro


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


def caminho_arquivo_recebido(registro: ArquivoRecebido) -> Path:
    caminho = Path(registro.caminho_arquivo)
    if not caminho.is_absolute():
        caminho = BACKEND_DIR / caminho
    caminho = caminho.resolve()
    if not caminho.is_relative_to(UPLOADS_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Caminho do arquivo de origem inválido.")
    if not caminho.is_file():
        raise HTTPException(status_code=404, detail="Arquivo original não encontrado.")
    return caminho


def detectar_adaptador(caminho: Path, extensao: str) -> tuple[object, bytes | str]:
    """Detecta qual adaptador reconhece o arquivo. Devolve o módulo do
    adaptador e o argumento já preparado para chamar sua função de parse.
    Levanta HTTPException(400) se nenhum ou mais de um adaptador reconhecer."""

    if extensao == ".txt":
        conteudo = caminho.read_bytes()
        encontrados = detectar_adaptadores_txt(conteudo)
        argumento_parse: bytes | str = conteudo
    elif extensao == ".xlsx":
        try:
            workbook = load_workbook(caminho, data_only=True)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Não foi possível ler o arquivo XLSX enviado.") from exc
        encontrados = detectar_adaptadores_xlsx(workbook)
        argumento_parse = str(caminho)
    else:
        raise HTTPException(status_code=400, detail="Envie um arquivo .txt ou .xlsx.")

    if not encontrados:
        raise HTTPException(
            status_code=400,
            detail="Formato de arquivo não reconhecido. Nenhum adaptador soube interpretar este arquivo.",
        )
    if len(encontrados) > 1:
        raise HTTPException(
            status_code=400,
            detail="Mais de um adaptador reconheceu este arquivo. Revise o conteúdo antes de importar.",
        )
    return encontrados[0], argumento_parse


def analisar_arquivo_salvo(db: Session, competencia: Competencia, registro: ArquivoRecebido) -> dict:
    caminho = caminho_arquivo_recebido(registro)
    extensao = Path(registro.nome_original).suffix.lower()
    funcionarios = db.query(Funcionario).filter(Funcionario.empresa_id == competencia.empresa_id).all()

    adaptador, argumento_parse = detectar_adaptador(caminho, extensao)

    try:
        resultado = FUNCOES_PARSE[adaptador.NOME_ADAPTER](
            argumento_parse,
            arquivo_nome=registro.nome_original,
            mes=competencia.mes,
            ano=competencia.ano,
            funcionarios=funcionarios,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    preview = resultado["registros"]
    # Preserva os adapters homologados, mas sinaliza associações divergentes
    # antes da seleção automática na prévia operacional.
    por_id = {f.id: f for f in funcionarios}
    def nome_comparavel(valor):
        texto = unicodedata.normalize("NFKD", str(valor or ""))
        return " ".join("".join(c for c in texto if not unicodedata.combining(c)).casefold().split())
    for item in preview:
        info = item["funcionario"]
        candidato = por_id.get(info.get("id"))
        if candidato and adaptador.NOME_ADAPTER.startswith("txt_"):
            codigo = info.get("codigo_origem")
            nome = info.get("nome_origem")
            divergente = (codigo and str(codigo) != str(candidato.codigo or "")) or (
                nome and nome_comparavel(nome) != nome_comparavel(candidato.nome)
            )
            if divergente:
                item["selecionado"] = False
                item["status"] = "conferir"
                item["pendencias"].append("ID ou nome diverge do cadastro sugerido; confirme a associação antes de selecionar este registro.")
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
    db.commit()
    for item in preview:
        item["origem"]["arquivo_id"] = registro.id

    funcionarios_encontrados = {
        item["funcionario"]["id"] for item in preview if item["funcionario"]["encontrado"]
    }
    funcionarios_nao_encontrados = {
        (item["funcionario"]["codigo_origem"], item["funcionario"]["nome_origem"])
        for item in preview
        if not item["funcionario"]["encontrado"]
    }
    return {
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
        "total_batidas": sum(len(item["batidas_originais"]) for item in preview),
        "total_dias": len(preview),
        "total_pendencias": sum(len(item["pendencias"]) for item in preview),
        "total_registros_com_pendencia": sum(1 for item in preview if item["pendencias"]),
        "registros_fora_competencia": sum(1 for item in preview if item["fora_da_competencia"]),
        "preview": preview,
    }


def hora_interpretada(valor: str | None) -> time | None:
    return time.fromisoformat(valor) if valor else None


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
        return analisar_arquivo_salvo(db, competencia, registro)
    except HTTPException as exc:
        registro.observacoes = f"Falha na análise do arquivo: {exc.detail}"
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
        raise


@router.post("/confirmar", status_code=status.HTTP_201_CREATED)
def confirmar_importacao(
    payload: ConfirmacaoImportacao,
    db: Session = Depends(get_db),
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

    analise = analisar_arquivo_salvo(db, competencia, arquivo)
    registros_por_id = {item["id"]: item for item in analise["preview"]}
    ids_selecionados = list(dict.fromkeys(payload.registros_ids))
    ids_invalidos = [registro_id for registro_id in ids_selecionados if registro_id not in registros_por_id]
    if ids_invalidos:
        raise HTTPException(status_code=400, detail="A seleção não corresponde à prévia atual do arquivo.")

    conflitos: list[dict] = []
    marcacoes: list[MarcacaoPonto] = []
    chaves_reservadas: set[tuple[int, date]] = set()
    for registro_id in ids_selecionados:
        item = registros_por_id[registro_id]
        funcionario_info = item["funcionario"]
        funcionario = db.get(Funcionario, funcionario_info["id"]) if funcionario_info["id"] else None
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
        existente = (
            db.query(MarcacaoPonto)
            .filter(
                MarcacaoPonto.competencia_id == competencia.id,
                MarcacaoPonto.funcionario_id == funcionario.id,
                MarcacaoPonto.data == data_marcacao,
            )
            .first()
        )
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

    arquivo.observacoes = (arquivo.observacoes or "") + (
        f" Confirmação: {datetime.now(timezone.utc).isoformat()}; {len(ids_selecionados)} dias solicitados; "
        f"{len(marcacoes)} importados; {len(conflitos)} conflitos."
    )
    if marcacoes or conflitos:
        if marcacoes:
            competencia.status = "em_conferencia"
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="A importação encontrou uma marcação duplicada. Nenhum registro foi sobrescrito.",
            ) from exc
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Não foi possível salvar a importação. Tente novamente.",
            ) from exc
        for marcacao in marcacoes:
            db.refresh(marcacao)

    return {
        "arquivo_id": arquivo.id,
        "competencia_id": competencia.id,
        "total_solicitados": len(ids_selecionados),
        "total_importados": len(marcacoes),
        "marcacoes_ids": [marcacao.id for marcacao in marcacoes],
        "total_conflitos": len(conflitos),
        "conflitos": conflitos,
    }
