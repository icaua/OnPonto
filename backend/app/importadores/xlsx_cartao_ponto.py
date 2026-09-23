from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.importadores.interpretacao_batidas import interpretar_batidas


NOME_ADAPTER = "xlsx_cartao_ponto"

COLUNAS_CABECALHO = (
    "Nome",
    "Sobrenome",
    "ID",
    "Departamento",
    "Grupo de presença",
    "Data",
    "Semana",
    "Horários de passagem de cartão",
)

LINHAS_VARREDURA_CABECALHO = 15
HORARIO_UNICO_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ErroImportacaoXlsxCartaoPonto(ValueError):
    """Erro esperado e apresentável durante a leitura deste XLSX de cartão de ponto."""

    def __init__(self, codigo: str, mensagem: str) -> None:
        self.codigo = codigo
        self.mensagem = mensagem
        super().__init__(mensagem)


def _normalizar_texto(valor: Any) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", texto).strip().casefold()


def _valor_funcionario(funcionario: Any, campo: str) -> Any:
    if isinstance(funcionario, Mapping):
        return funcionario.get(campo)
    return getattr(funcionario, campo, None)


def _indexar_funcionarios(
    funcionarios: Iterable[Any],
) -> tuple[dict[str, list[Any]], dict[str, list[Any]]]:
    por_codigo: dict[str, list[Any]] = {}
    por_nome: dict[str, list[Any]] = {}

    for funcionario in funcionarios:
        codigo_bruto = _valor_funcionario(funcionario, "codigo")
        codigo = "" if codigo_bruto is None else str(codigo_bruto).strip()
        nome = _normalizar_texto(_valor_funcionario(funcionario, "nome"))
        if codigo:
            por_codigo.setdefault(codigo, []).append(funcionario)
        if nome:
            por_nome.setdefault(nome, []).append(funcionario)

    return por_codigo, por_nome


def _localizar_funcionario(
    codigo: str | None,
    nome: str,
    por_codigo: dict[str, list[Any]],
    por_nome: dict[str, list[Any]],
) -> Any | None:
    if codigo:
        candidatos_codigo = por_codigo.get(codigo, [])
        if len(candidatos_codigo) == 1:
            return candidatos_codigo[0]

    candidatos_nome = por_nome.get(_normalizar_texto(nome), [])
    if len(candidatos_nome) == 1:
        return candidatos_nome[0]
    return None


def _indices_cabecalho(valores: list[Any]) -> dict[str, int] | None:
    indices: dict[str, int] = {}
    for indice, valor in enumerate(valores):
        normalizado = _normalizar_texto(valor)
        if normalizado:
            indices.setdefault(normalizado, indice)

    obrigatorias = {_normalizar_texto(coluna) for coluna in COLUNAS_CABECALHO}
    if not obrigatorias.issubset(indices):
        return None
    return indices


def _localizar_cabecalho(ws: Worksheet) -> tuple[int, dict[str, int]] | None:
    limite = min(ws.max_row, LINHAS_VARREDURA_CABECALHO)
    for row_idx in range(1, limite + 1):
        valores = [ws.cell(row_idx, col).value for col in range(1, ws.max_column + 1)]
        indices = _indices_cabecalho(valores)
        if indices is not None:
            return row_idx, indices
    return None


def detectar(workbook: Workbook) -> bool:
    """Checagem estrutural barata: alguma planilha tem, nas primeiras linhas,
    um cabeçalho contendo todas as colunas esperadas do cartão de ponto."""

    return any(_localizar_cabecalho(ws) is not None for ws in workbook.worksheets)


def _extrair_data(valor: Any) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor or "").strip()
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return None


def _extrair_nome_completo(nome: Any, sobrenome: Any) -> str:
    nome_texto = re.sub(r"\s+", " ", str(nome or "")).strip()
    sobrenome_texto = re.sub(r"\s+", " ", str(sobrenome or "")).strip()
    if not sobrenome_texto or sobrenome_texto == "-":
        return nome_texto
    return f"{nome_texto} {sobrenome_texto}".strip()


def _extrair_horarios(valores: list[Any], desde_indice: int) -> list[str]:
    """Procura, a partir da coluna de horários (inclusive) até a última coluna
    da linha, o primeiro valor estruturalmente compatível com uma lista de
    horários separados por ';'. Nesta planilha real, o rótulo da coluna
    'Horários de passagem de cartão' não corresponde ao seu próprio conteúdo
    (que é uma contagem); os horários de fato ficam na coluna seguinte."""

    for indice in range(len(valores) - 1, desde_indice - 1, -1):
        texto = str(valores[indice] or "").strip()
        if not texto:
            continue
        partes = [parte.strip() for parte in texto.split(";")]
        if partes and all(HORARIO_UNICO_RE.match(parte) for parte in partes):
            return partes
    return []


def _id_registro(
    arquivo_nome: str,
    chave_funcionario: tuple[str, str],
    funcionario_id: Any | None,
    data_registro: str,
    batidas: list[str],
) -> str:
    conteudo = json.dumps(
        {
            "arquivo": arquivo_nome,
            "funcionario": chave_funcionario,
            "funcionario_resolvido": funcionario_id,
            "data": data_registro,
            "batidas": batidas,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    digest = hashlib.sha256(conteudo.encode("utf-8")).hexdigest()[:20]
    return f"{NOME_ADAPTER}-{digest}"


def parse_xlsx_cartao_ponto(
    file_path: str,
    *,
    arquivo_nome: str,
    mes: int,
    ano: int,
    funcionarios: Iterable[Any] = (),
) -> dict[str, Any]:
    """Lê um XLSX no layout 'longo' (uma linha por funcionário-por-dia, com
    todos os horários do dia numa célula só, separados por ';')."""

    caminho = Path(file_path)
    workbook = load_workbook(caminho, data_only=True)

    alvo = None
    for ws in workbook.worksheets:
        localizado = _localizar_cabecalho(ws)
        if localizado is not None:
            alvo = (ws, *localizado)
            break
    if alvo is None:
        raise ErroImportacaoXlsxCartaoPonto(
            "cabecalho_incompativel",
            "Não foi possível localizar o cabeçalho esperado do cartão de ponto.",
        )
    ws, linha_cabecalho, indices = alvo

    indice_nome = indices[_normalizar_texto("Nome")]
    indice_sobrenome = indices[_normalizar_texto("Sobrenome")]
    indice_id = indices[_normalizar_texto("ID")]
    indice_data = indices[_normalizar_texto("Data")]
    indice_horarios = indices[_normalizar_texto("Horários de passagem de cartão")]

    por_codigo, por_nome = _indexar_funcionarios(funcionarios)
    nome_arquivo = str(arquivo_nome)
    registros = []
    total_linhas_validas = 0

    for row_idx in range(linha_cabecalho + 1, ws.max_row + 1):
        valores = [ws.cell(row_idx, col).value for col in range(1, ws.max_column + 1)]
        if not any(str(valor).strip() for valor in valores if valor is not None):
            continue

        codigo = str(valores[indice_id] or "").strip() or None
        nome_completo = _extrair_nome_completo(valores[indice_nome], valores[indice_sobrenome])
        if not nome_completo:
            raise ErroImportacaoXlsxCartaoPonto(
                "linha_invalida", f"O nome do funcionário está vazio na linha {row_idx}."
            )

        data_marcacao = _extrair_data(valores[indice_data])
        if data_marcacao is None:
            raise ErroImportacaoXlsxCartaoPonto(
                "data_invalida", f"Data inválida na linha {row_idx}: {valores[indice_data]!r}."
            )

        horarios = _extrair_horarios(valores, indice_horarios)
        total_linhas_validas += 1

        resultado_interpretacao = interpretar_batidas(horarios)
        interpretacao = {
            "entrada": resultado_interpretacao["entrada"],
            "saida_intervalo": resultado_interpretacao["saida_almoco"],
            "retorno_intervalo": resultado_interpretacao["retorno_almoco"],
            "saida": resultado_interpretacao["saida"],
        }
        status = "nao_conferido" if resultado_interpretacao["status"] == "normal" else "conferir"
        pendencias = [resultado_interpretacao["observacoes"]] if resultado_interpretacao["observacoes"] else []

        chave_funcionario = ("codigo", codigo) if codigo else ("nome", _normalizar_texto(nome_completo))
        funcionario = _localizar_funcionario(codigo, nome_completo, por_codigo, por_nome)
        funcionario_id = _valor_funcionario(funcionario, "id") if funcionario is not None else None
        encontrado = funcionario is not None and funcionario_id is not None
        nome_cadastrado = _valor_funcionario(funcionario, "nome") if encontrado else None
        fora_da_competencia = data_marcacao.month != mes or data_marcacao.year != ano

        if not encontrado:
            pendencias.append("Funcionário não cadastrado para esta empresa")
        if fora_da_competencia:
            pendencias.append("Data fora da competência selecionada")

        data_iso = data_marcacao.isoformat()
        registros.append(
            {
                "id": _id_registro(
                    nome_arquivo,
                    chave_funcionario,
                    funcionario_id if encontrado else None,
                    data_iso,
                    horarios,
                ),
                "funcionario": {
                    "id": funcionario_id if encontrado else None,
                    "codigo_origem": codigo,
                    "nome_origem": nome_completo,
                    "nome_cadastrado": nome_cadastrado,
                    "encontrado": encontrado,
                },
                "data": data_iso,
                "batidas_originais": horarios,
                "interpretacao": interpretacao,
                "status": status,
                "pendencias": pendencias,
                "fora_da_competencia": fora_da_competencia,
                "selecionado": encontrado and not fora_da_competencia,
                "origem": {"tipo": NOME_ADAPTER, "arquivo": nome_arquivo},
            }
        )

    if not total_linhas_validas:
        raise ErroImportacaoXlsxCartaoPonto(
            "arquivo_vazio", "O arquivo XLSX não contém registros de ponto."
        )

    registros.sort(key=lambda item: (_normalizar_texto(item["funcionario"]["nome_origem"]), item["data"]))

    return {"total_linhas_validas": total_linhas_validas, "registros": registros}
