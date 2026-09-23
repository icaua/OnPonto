from __future__ import annotations

import codecs
import csv
import hashlib
import io
import json
import os
import re
import unicodedata
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.importadores.interpretacao_batidas import interpretar_batidas


NOME_ADAPTER = "txt_log_relogio"
COLUNAS_OBRIGATORIAS = ("EnNo", "Name", "DateTime")
FORMATO_DATA_HORA = "%Y-%m-%d %H:%M:%S"

_PENDENCIA_UMA_BATIDA = "Apenas uma batida encontrada"
_PENDENCIA_DUAS_BATIDAS = "Apenas duas batidas encontradas"
_PENDENCIA_QUANTIDADE_IMPAR = "Quantidade ímpar de batidas"
_PENDENCIA_MAIS_DE_QUATRO = "Mais de quatro batidas encontradas"


class ErroImportacaoTxt(ValueError):
    """Erro esperado e apresentável durante a leitura do TXT de relógio."""

    def __init__(self, codigo: str, mensagem: str) -> None:
        self.codigo = codigo
        self.mensagem = mensagem
        super().__init__(mensagem)


def _ler_bytes(fonte: bytes | bytearray | os.PathLike[str] | str) -> bytes:
    if isinstance(fonte, (bytes, bytearray)):
        return bytes(fonte)
    if isinstance(fonte, (str, os.PathLike)):
        try:
            return Path(fonte).read_bytes()
        except OSError as exc:
            raise ErroImportacaoTxt(
                "erro_leitura",
                "Não foi possível ler o arquivo TXT informado.",
            ) from exc
    raise ErroImportacaoTxt(
        "fonte_invalida",
        "A fonte do TXT deve ser conteúdo em bytes ou um caminho de arquivo.",
    )


def _parece_utf16_sem_bom(dados: bytes) -> str | None:
    amostra = dados[:4096]
    if len(amostra) < 4:
        return None

    bytes_pares = amostra[0::2]
    bytes_impares = amostra[1::2]
    if not bytes_pares or not bytes_impares:
        return None

    nulos_pares = bytes_pares.count(0) / len(bytes_pares)
    nulos_impares = bytes_impares.count(0) / len(bytes_impares)
    if nulos_impares >= 0.25 and nulos_impares - nulos_pares >= 0.20:
        return "utf-16-le"
    if nulos_pares >= 0.25 and nulos_pares - nulos_impares >= 0.20:
        return "utf-16-be"
    return None


def _decodificar(dados: bytes) -> tuple[str, str]:
    if not dados:
        raise ErroImportacaoTxt("arquivo_vazio", "O arquivo TXT está vazio.")

    if dados.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        tentativas = (("utf-16", "utf-16"),)
    else:
        utf16_sem_bom = _parece_utf16_sem_bom(dados)
        if utf16_sem_bom:
            tentativas = ((utf16_sem_bom, utf16_sem_bom),)
        elif dados.startswith(codecs.BOM_UTF8):
            tentativas = (("utf-8-sig", "utf-8-sig"),)
        else:
            tentativas = (("utf-8", "utf-8"),)

    for codec, rotulo in tentativas:
        try:
            texto = dados.decode(codec, errors="strict")
        except UnicodeError:
            continue
        if "\x00" not in texto:
            return texto, rotulo

    raise ErroImportacaoTxt(
        "encoding_nao_reconhecido",
        "Não foi possível reconhecer a codificação do arquivo. Use UTF-16 ou UTF-8.",
    )


def _normalizar_nome(valor: Any) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", texto).strip().casefold()


def _normalizar_cabecalho(valor: str) -> str:
    return re.sub(r"\s+", "", valor).casefold()


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
        nome = _normalizar_nome(_valor_funcionario(funcionario, "nome"))
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

    candidatos_nome = por_nome.get(_normalizar_nome(nome), [])
    if len(candidatos_nome) == 1:
        return candidatos_nome[0]
    return None


def _interpretar_batidas(batidas: list[str]) -> tuple[dict[str, str | None], str, list[str]]:
    resultado = interpretar_batidas([batida[:5] for batida in batidas])
    interpretacao: dict[str, str | None] = {
        "entrada": resultado["entrada"],
        "saida_intervalo": resultado["saida_almoco"],
        "retorno_intervalo": resultado["retorno_almoco"],
        "saida": resultado["saida"],
    }

    quantidade = len(batidas)
    if quantidade == 4:
        return interpretacao, "nao_conferido", []
    if quantidade == 1:
        return interpretacao, "conferir", [_PENDENCIA_UMA_BATIDA]
    if quantidade == 2:
        return interpretacao, "conferir", [_PENDENCIA_DUAS_BATIDAS]
    if quantidade == 3:
        return interpretacao, "conferir", [_PENDENCIA_QUANTIDADE_IMPAR]
    return interpretacao, "conferir", [_PENDENCIA_MAIS_DE_QUATRO]


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
    return f"txt-{digest}"


def detectar(conteudo: bytes) -> bool:
    """Checagem estrutural barata: cabeçalho com as colunas EnNo, Name e DateTime."""

    try:
        texto, _encoding = _decodificar(conteudo)
    except ErroImportacaoTxt:
        return False
    if not texto.strip():
        return False
    try:
        leitor = csv.reader(io.StringIO(texto, newline=""), delimiter="\t", strict=True)
        linhas = list(leitor)
    except csv.Error:
        return False

    indice_cabecalho = next(
        (indice for indice, linha in enumerate(linhas) if any(celula.strip() for celula in linha)),
        None,
    )
    if indice_cabecalho is None:
        return False

    colunas = {_normalizar_cabecalho(coluna) for coluna in linhas[indice_cabecalho]}
    obrigatorias = {_normalizar_cabecalho(coluna) for coluna in COLUNAS_OBRIGATORIAS}
    return obrigatorias.issubset(colunas)


def _validar_competencia(mes: int, ano: int) -> None:
    if isinstance(mes, bool) or not isinstance(mes, int) or not 1 <= mes <= 12:
        raise ErroImportacaoTxt("competencia_invalida", "O mês da competência é inválido.")
    if isinstance(ano, bool) or not isinstance(ano, int) or ano < 1:
        raise ErroImportacaoTxt("competencia_invalida", "O ano da competência é inválido.")


def parse_txt_log_relogio(
    fonte: bytes | bytearray | os.PathLike[str] | str,
    *,
    arquivo_nome: str,
    mes: int,
    ano: int,
    funcionarios: Iterable[Any] = (),
) -> dict[str, Any]:
    """Lê um TXT TAB de relógio e devolve registros diários normalizados."""

    _validar_competencia(mes, ano)
    dados = _ler_bytes(fonte)
    texto, encoding = _decodificar(dados)
    if not texto.strip():
        raise ErroImportacaoTxt("arquivo_vazio", "O arquivo TXT está vazio.")

    try:
        leitor = csv.reader(io.StringIO(texto, newline=""), delimiter="\t", strict=True)
        linhas = list(leitor)
    except csv.Error as exc:
        raise ErroImportacaoTxt("txt_invalido", "O arquivo TXT possui estrutura inválida.") from exc

    indice_cabecalho = next(
        (indice for indice, linha in enumerate(linhas) if any(celula.strip() for celula in linha)),
        None,
    )
    if indice_cabecalho is None:
        raise ErroImportacaoTxt("arquivo_vazio", "O arquivo TXT está vazio.")

    cabecalho = linhas[indice_cabecalho]
    indices_colunas: dict[str, int] = {}
    for indice, coluna in enumerate(cabecalho):
        indices_colunas.setdefault(_normalizar_cabecalho(coluna), indice)

    ausentes = [
        coluna
        for coluna in COLUNAS_OBRIGATORIAS
        if _normalizar_cabecalho(coluna) not in indices_colunas
    ]
    if ausentes:
        raise ErroImportacaoTxt(
            "cabecalho_incompativel",
            "Cabeçalho incompatível. Colunas obrigatórias ausentes: " + ", ".join(ausentes) + ".",
        )

    indice_codigo = indices_colunas[_normalizar_cabecalho("EnNo")]
    indice_nome = indices_colunas[_normalizar_cabecalho("Name")]
    indice_data_hora = indices_colunas[_normalizar_cabecalho("DateTime")]
    maior_indice = max(indice_codigo, indice_nome, indice_data_hora)

    grupos: dict[tuple[tuple[str, str], date], dict[str, Any]] = {}
    total_linhas_validas = 0
    for deslocamento, linha in enumerate(linhas[indice_cabecalho + 1 :], start=indice_cabecalho + 2):
        if not any(celula.strip() for celula in linha):
            continue
        if len(linha) <= maior_indice:
            raise ErroImportacaoTxt(
                "linha_invalida",
                f"A linha {deslocamento} não possui todas as colunas obrigatórias.",
            )

        codigo = linha[indice_codigo].strip() or None
        nome = linha[indice_nome].strip()
        data_hora_texto = linha[indice_data_hora].strip()
        if not nome:
            raise ErroImportacaoTxt(
                "linha_invalida",
                f"O nome do funcionário está vazio na linha {deslocamento}.",
            )

        try:
            data_hora = datetime.strptime(data_hora_texto, FORMATO_DATA_HORA)
        except ValueError as exc:
            raise ErroImportacaoTxt(
                "datetime_invalido",
                f"DateTime inválido na linha {deslocamento}: {data_hora_texto or '(vazio)'}.",
            ) from exc

        chave_funcionario = ("codigo", codigo) if codigo else ("nome", _normalizar_nome(nome))
        chave_grupo = (chave_funcionario, data_hora.date())
        grupo = grupos.setdefault(
            chave_grupo,
            {
                "chave_funcionario": chave_funcionario,
                "codigo": codigo,
                "nome": nome,
                "data": data_hora.date(),
                "batidas": [],
            },
        )
        grupo["batidas"].append(data_hora)
        total_linhas_validas += 1

    if not total_linhas_validas:
        raise ErroImportacaoTxt("arquivo_vazio", "O arquivo TXT não contém registros de ponto.")

    por_codigo, por_nome = _indexar_funcionarios(funcionarios)
    nome_arquivo = str(arquivo_nome)
    registros = []
    grupos_ordenados = sorted(
        grupos.values(),
        key=lambda item: (_normalizar_nome(item["nome"]), item["codigo"] or "", item["data"]),
    )

    for grupo in grupos_ordenados:
        batidas = [valor.strftime("%H:%M:%S") for valor in sorted(grupo["batidas"])]
        interpretacao, status, pendencias = _interpretar_batidas(batidas)
        funcionario = _localizar_funcionario(grupo["codigo"], grupo["nome"], por_codigo, por_nome)
        funcionario_id = _valor_funcionario(funcionario, "id") if funcionario is not None else None
        encontrado = funcionario is not None and funcionario_id is not None
        nome_cadastrado = _valor_funcionario(funcionario, "nome") if encontrado else None
        fora_da_competencia = grupo["data"].month != mes or grupo["data"].year != ano

        if not encontrado:
            pendencias.append("Funcionário não cadastrado para esta empresa")
        if fora_da_competencia:
            pendencias.append("Data fora da competência selecionada")

        data_iso = grupo["data"].isoformat()
        registros.append(
            {
                "id": _id_registro(
                    nome_arquivo,
                    grupo["chave_funcionario"],
                    funcionario_id if encontrado else None,
                    data_iso,
                    batidas,
                ),
                "funcionario": {
                    "id": funcionario_id if encontrado else None,
                    "codigo_origem": grupo["codigo"],
                    "nome_origem": grupo["nome"],
                    "nome_cadastrado": nome_cadastrado,
                    "encontrado": encontrado,
                },
                "data": data_iso,
                "batidas_originais": batidas,
                "interpretacao": interpretacao,
                "status": status,
                "pendencias": pendencias,
                "fora_da_competencia": fora_da_competencia,
                "selecionado": encontrado and not fora_da_competencia,
                "origem": {"tipo": "txt_log_relogio", "arquivo": nome_arquivo},
            }
        )

    return {
        "encoding": encoding,
        "total_linhas_validas": total_linhas_validas,
        "registros": registros,
    }
