from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet


HORARIO_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")


def normalizar_texto(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    texto = re.sub(r"\s+", " ", texto)
    return texto.upper()


def texto_limpo(valor: Any) -> str:
    if valor is None:
        return ""
    return re.sub(r"\s+", " ", str(valor).strip())


def construir_lookup_mescladas(ws: Worksheet) -> dict[tuple[int, int], Any]:
    lookup: dict[tuple[int, int], Any] = {}
    for faixa in ws.merged_cells.ranges:
        valor = ws.cell(faixa.min_row, faixa.min_col).value
        for row in range(faixa.min_row, faixa.max_row + 1):
            for col in range(faixa.min_col, faixa.max_col + 1):
                lookup[(row, col)] = valor
    return lookup


def valor_celula(ws: Worksheet, row: int, col: int, lookup_mescladas: dict[tuple[int, int], Any]) -> Any:
    valor = ws.cell(row, col).value
    if valor is None:
        return lookup_mescladas.get((row, col))
    return valor


def valores_linha(ws: Worksheet, row: int, lookup_mescladas: dict[tuple[int, int], Any]) -> list[Any]:
    return [valor_celula(ws, row, col, lookup_mescladas) for col in range(1, ws.max_column + 1)]


def linha_eh_inicio_bloco(valores: list[Any]) -> bool:
    return any("NUMERO DE FUNCI" in normalizar_texto(valor) for valor in valores)


def extrair_codigo_funcionario(valores: list[Any]) -> str | None:
    for valor in valores:
        if "NUMERO DE FUNCI" not in normalizar_texto(valor):
            continue
        numeros = re.findall(r"\d+", str(valor))
        if numeros:
            return numeros[-1].lstrip("0") or "0"
    return None


def eh_rotulo_nome(valor: Any) -> bool:
    normalizado = normalizar_texto(valor)
    return bool(re.search(r"\bNOME\b", normalizado))


def eh_valor_nome(valor: Any) -> bool:
    normalizado = normalizar_texto(valor)
    if not normalizado:
        return False
    rotulos_invalidos = ["NUMERO DE FUNCI", "DEPARTAMENTO", "UNSET"]
    return not any(rotulo in normalizado for rotulo in rotulos_invalidos) and normalizado != "NOME"


def extrair_nome_funcionario(valores: list[Any], linha: int) -> str:
    for indice, valor in enumerate(valores):
        if not eh_rotulo_nome(valor):
            continue

        texto = texto_limpo(valor)
        inline = re.split(r"\bNOME\b\s*[:\-]?\s*", texto, flags=re.IGNORECASE, maxsplit=1)
        if len(inline) == 2 and eh_valor_nome(inline[1]):
            return inline[1]

        for candidato in valores[indice + 1 :]:
            if eh_valor_nome(candidato):
                return texto_limpo(candidato)

    return f"Funcionário sem nome linha {linha}"


def extrair_dia(valor: Any) -> int | None:
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, int):
        return valor if 1 <= valor <= 31 else None
    if isinstance(valor, float) and valor.is_integer():
        dia = int(valor)
        return dia if 1 <= dia <= 31 else None
    texto = texto_limpo(valor)
    if re.fullmatch(r"\d{1,2}", texto):
        dia = int(texto)
        return dia if 1 <= dia <= 31 else None
    return None


def formatar_hora(valor: time) -> str:
    return f"{valor.hour:02d}:{valor.minute:02d}"


def extrair_horarios(valor: Any) -> list[str]:
    if value_is_time(valor):
        return [formatar_hora(valor)]
    if isinstance(valor, datetime):
        return [formatar_hora(valor.time())]

    texto = str(valor or "")
    horarios = []
    for match in HORARIO_RE.finditer(texto):
        hora = int(match.group(1))
        minuto = int(match.group(2))
        horarios.append(f"{hora:02d}:{minuto:02d}")
    return horarios


def value_is_time(valor: Any) -> bool:
    return isinstance(valor, time) and not isinstance(valor, datetime)


def montar_marcacao(data_marcacao: date, horarios: list[str]) -> dict[str, Any]:
    marcacao = {
        "data": data_marcacao.isoformat(),
        "entrada": None,
        "saida_almoco": None,
        "retorno_almoco": None,
        "saida": None,
        "status": "pendente",
        "status_dia": "pendente",
        "observacoes": "Sem marcações",
        "horarios_extraidos": horarios,
    }

    if len(horarios) >= 4:
        marcacao.update(
            {
                "entrada": horarios[0],
                "saida_almoco": horarios[1],
                "retorno_almoco": horarios[2],
                "saida": horarios[3],
                "status": "normal" if len(horarios) == 4 else "pendente_conferencia",
                "status_dia": "normal" if len(horarios) == 4 else "pendente_conferencia",
                "observacoes": None if len(horarios) == 4 else "Mais de quatro marcações encontradas",
            }
        )
    elif len(horarios) == 2:
        marcacao.update(
            {
                "entrada": horarios[0],
                "saida": horarios[1],
                "status": "pendente_conferencia",
                "status_dia": "pendente_conferencia",
                "observacoes": "Apenas duas marcações encontradas",
            }
        )
    elif len(horarios) in {1, 3}:
        campos = ["entrada", "saida_almoco", "retorno_almoco"]
        for campo, horario in zip(campos, horarios):
            marcacao[campo] = horario
        marcacao.update(
            {
                "status": "pendente_conferencia",
                "status_dia": "pendente_conferencia",
                "observacoes": "Quantidade incompleta de marcações",
            }
        )

    return marcacao


def parse_xlsx_ponto_generico(file_path: str, mes: int, ano: int, empresa_id: int) -> list[dict[str, Any]]:
    caminho = Path(file_path)
    workbook = load_workbook(caminho, data_only=True)
    funcionarios: list[dict[str, Any]] = []

    for ws in workbook.worksheets:
        lookup_mescladas = construir_lookup_mescladas(ws)

        for row_idx in range(1, max(ws.max_row - 1, 1)):
            valores_header = valores_linha(ws, row_idx, lookup_mescladas)
            if not linha_eh_inicio_bloco(valores_header):
                continue

            codigo = extrair_codigo_funcionario(valores_header)
            nome = extrair_nome_funcionario(valores_header, row_idx)
            linha_marcacoes = row_idx + 1
            linha_dias = row_idx + 2
            marcacoes = []

            for col_idx in range(1, ws.max_column + 1):
                dia = extrair_dia(valor_celula(ws, linha_dias, col_idx, lookup_mescladas))
                if dia is None:
                    continue
                try:
                    data_marcacao = date(ano, mes, dia)
                except ValueError:
                    continue

                valor_marcacoes = valor_celula(ws, linha_marcacoes, col_idx, lookup_mescladas)
                horarios = extrair_horarios(valor_marcacoes)
                marcacoes.append(montar_marcacao(data_marcacao, horarios))

            funcionarios.append(
                {
                    "empresa_id": empresa_id,
                    "codigo": codigo,
                    "nome": nome,
                    "sheet": ws.title,
                    "linha_cabecalho": row_idx,
                    "marcacoes": marcacoes,
                }
            )

    return funcionarios
