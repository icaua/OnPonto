import json
import re
import unicodedata
from datetime import date, datetime, time
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.competencias.service import exigir_competencia_editavel
from app.database.models import ArquivoRecebido, Competencia, Empresa, Funcionario, MarcacaoPonto
from app.database.session import BACKEND_DIR, UPLOADS_DIR, get_db
from app.importadores.schemas import ConfirmacaoImportacaoTxt
from app.importadores.txt_log_relogio import ErroImportacaoTxt, parse_txt_log_relogio
from app.importadores.xlsx_ponto_generico import parse_xlsx_ponto_generico


router = APIRouter(prefix="/importadores", tags=["Importadores"])
LIMITE_ARQUIVO_BYTES = 25 * 1024 * 1024


def nome_seguro(nome: str) -> str:
    base = Path(nome).name.strip() or "arquivo.xlsx"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base)


def chave_texto(valor: str | None) -> str:
    texto = unicodedata.normalize("NFKD", valor or "")
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    texto = re.sub(r"\s+", " ", texto).strip().lower()
    return texto


def salvar_arquivo_original(
    db: Session,
    competencia: Competencia,
    arquivo: UploadFile,
    *,
    extensao_esperada: str = ".xlsx",
    tipo_arquivo: str = "xlsx",
    observacoes: str = "Arquivo importado pelo importador XLSX genérico.",
) -> ArquivoRecebido:
    original = nome_seguro(arquivo.filename or f"ponto{extensao_esperada}")
    extensao = Path(original).suffix.lower()
    if extensao != extensao_esperada:
        raise HTTPException(status_code=400, detail=f"Envie um arquivo {extensao_esperada}.")

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


def analisar_txt_salvo(db: Session, competencia: Competencia, registro: ArquivoRecebido) -> dict:
    funcionarios = db.query(Funcionario).filter(Funcionario.empresa_id == competencia.empresa_id).all()
    try:
        resultado = parse_txt_log_relogio(
            caminho_arquivo_recebido(registro),
            arquivo_nome=registro.nome_original,
            mes=competencia.mes,
            ano=competencia.ano,
            funcionarios=funcionarios,
        )
    except ErroImportacaoTxt as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Não foi possível ler o arquivo TXT enviado.") from exc

    preview = resultado["registros"]
    for item in preview:
        item["origem"]["arquivo_id"] = registro.id
        if not item["funcionario"]["encontrado"]:
            aviso = "Funcionário não cadastrado para esta empresa"
            if aviso not in item["pendencias"]:
                item["pendencias"].append(aviso)
        if item["fora_da_competencia"]:
            aviso = "Data fora da competência selecionada"
            if aviso not in item["pendencias"]:
                item["pendencias"].append(aviso)
        item["selecionado"] = bool(item["funcionario"]["encontrado"] and not item["fora_da_competencia"])

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
        "tipo_detectado": "txt_log_relogio",
        "encoding": resultado["encoding"],
        "empresa_id": competencia.empresa_id,
        "competencia_id": competencia.id,
        "total_linhas_validas": resultado["total_linhas_validas"],
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


def mapa_funcionarios(db: Session, empresa_id: int) -> tuple[dict[str, Funcionario], dict[str, Funcionario]]:
    funcionarios = db.query(Funcionario).filter(Funcionario.empresa_id == empresa_id).all()
    por_codigo = {str(funcionario.codigo).strip(): funcionario for funcionario in funcionarios if funcionario.codigo}
    por_nome = {chave_texto(funcionario.nome): funcionario for funcionario in funcionarios}
    return por_codigo, por_nome


def enriquecer_previa(
    parsed: list[dict],
    competencia: Competencia,
    db: Session,
) -> tuple[list[dict], list[dict]]:
    por_codigo, por_nome = mapa_funcionarios(db, competencia.empresa_id)
    funcionarios_preview = []
    marcacoes_preview = []

    for funcionario_parse in parsed:
        codigo = funcionario_parse.get("codigo")
        nome = funcionario_parse.get("nome")
        funcionario = None
        if codigo:
            funcionario = por_codigo.get(str(codigo).strip())
        if not funcionario:
            funcionario = por_nome.get(chave_texto(nome))

        funcionario_preview = {
            **funcionario_parse,
            "funcionario_id": funcionario.id if funcionario else None,
            "funcionario_encontrado": funcionario is not None,
        }
        funcionarios_preview.append(funcionario_preview)

        for marcacao in funcionario_parse["marcacoes"]:
            observacoes = marcacao.get("observacoes")
            if not funcionario:
                aviso = "Funcionário não cadastrado para esta empresa"
                observacoes = f"{observacoes}; {aviso}" if observacoes else aviso
            marcacoes_preview.append(
                {
                    "competencia_id": competencia.id,
                    "empresa_id": competencia.empresa_id,
                    "funcionario_id": funcionario.id if funcionario else None,
                    "funcionario_encontrado": funcionario is not None,
                    "funcionario": nome,
                    "codigo": codigo,
                    "data": marcacao["data"],
                    "entrada": marcacao["entrada"],
                    "saida_almoco": marcacao["saida_almoco"],
                    "retorno_almoco": marcacao["retorno_almoco"],
                    "saida": marcacao["saida"],
                    "status": marcacao["status"],
                    "status_dia": marcacao["status_dia"],
                    "origem": "xlsx_importado",
                    "conferido": False,
                    "observacoes": observacoes,
                    "horarios_extraidos": marcacao["horarios_extraidos"],
                }
            )

    return funcionarios_preview, marcacoes_preview


@router.post("/xlsx-ponto-generico", status_code=status.HTTP_201_CREATED)
def importar_xlsx_ponto_generico(
    competencia_id: int = Form(...),
    empresa_id: int = Form(...),
    mes: int = Form(...),
    ano: int = Form(...),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    empresa, competencia = validar_contexto_importacao(db, empresa_id, competencia_id)
    if competencia.mes != mes or competencia.ano != ano:
        raise HTTPException(status_code=400, detail="Mês/ano não correspondem à competência informada.")

    registro = salvar_arquivo_original(db, competencia, arquivo)
    caminho_arquivo = BACKEND_DIR / registro.caminho_arquivo
    parsed = parse_xlsx_ponto_generico(str(caminho_arquivo), mes=mes, ano=ano, empresa_id=empresa_id)
    funcionarios_preview, marcacoes_preview = enriquecer_previa(parsed, competencia, db)

    return {
        "arquivo": {
            "id": registro.id,
            "nome_original": registro.nome_original,
            "caminho_arquivo": registro.caminho_arquivo,
        },
        "competencia_id": competencia.id,
        "empresa_id": empresa.id,
        "total_funcionarios": len(funcionarios_preview),
        "total_marcacoes": len(marcacoes_preview),
        "total_salvaveis": sum(1 for item in marcacoes_preview if item["funcionario_id"]),
        "funcionarios": funcionarios_preview,
        "marcacoes": marcacoes_preview,
    }


@router.post("/txt-log-relogio/analisar", status_code=status.HTTP_201_CREATED)
def analisar_txt_log_relogio(
    competencia_id: int = Form(...),
    empresa_id: int = Form(...),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    _, competencia = validar_contexto_importacao(db, empresa_id, competencia_id)
    registro = salvar_arquivo_original(
        db,
        competencia,
        arquivo,
        extensao_esperada=".txt",
        tipo_arquivo="txt_log_relogio",
        observacoes="Arquivo original preservado para análise do log TXT do relógio.",
    )
    try:
        return analisar_txt_salvo(db, competencia, registro)
    except HTTPException as exc:
        registro.observacoes = f"Falha na análise do TXT: {exc.detail}"
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
        raise


@router.post("/txt-log-relogio/confirmar", status_code=status.HTTP_201_CREATED)
def confirmar_txt_log_relogio(
    payload: ConfirmacaoImportacaoTxt,
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
    if arquivo.tipo_arquivo != "txt_log_relogio" or Path(arquivo.nome_original).suffix.lower() != ".txt":
        raise HTTPException(status_code=400, detail="Arquivo informado não é um TXT de relógio analisável.")

    analise = analisar_txt_salvo(db, competencia, arquivo)
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
        if existente:
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
        marcacao = MarcacaoPonto(
            competencia_id=competencia.id,
            funcionario_id=funcionario.id,
            data=data_marcacao,
            entrada=hora_interpretada(interpretacao.get("entrada")),
            saida_almoco=hora_interpretada(interpretacao.get("saida_intervalo")),
            retorno_almoco=hora_interpretada(interpretacao.get("retorno_intervalo")),
            saida=hora_interpretada(interpretacao.get("saida")),
            status_dia="normal" if item["status"] == "nao_conferido" else "pendente_conferencia",
            origem="txt_log_relogio",
            conferido=False,
            observacoes="; ".join(item["pendencias"]) or None,
            batidas_originais=json.dumps(item["batidas_originais"], ensure_ascii=False),
            arquivo_origem_id=arquivo.id,
        )
        chaves_reservadas.add(chave_marcacao)
        db.add(marcacao)
        marcacoes.append(marcacao)

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
