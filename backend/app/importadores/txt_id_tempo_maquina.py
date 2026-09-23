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

from app.importadores import txt_log_relogio
from app.importadores.interpretacao_batidas import interpretar_batidas


NOME_ADAPTER = "txt_id_tempo_maquina"
COLUNAS_OBRIGATORIAS = ("ID", "Nome", "Tempo")

# Confirmados em arquivos reais recebidos: ID / Tra. No., Nome e Tempo.
ALIASES_ID = {"id", "trano"}
ALIASES_NOME = {"nome"}
ALIASES_TEMPO = {"tempo"}

# Plausíveis para ZKTeco e compatíveis; ainda sem confirmação em arquivo real.
# Tokens sem acentos, espaços ou pontuação, conforme _normalizar_cabecalho.
# Este vocabulário cobre só os três papéis deste layout; o TXT genérico possui
# outros papéis e formatos, portanto não herdamos toda a sua lista de aliases.
ALIASES_ID |= {
    "matricula", "cod", "codigo", "numero", "num",
    "enno", "enrollnumber", "enrollno",
    "empid", "employeeid", "userid", "userno",
    "badgeno", "badgenumber", "pin", "acno", "personid",
}
ALIASES_NOME |= {"name", "funcionario", "colaborador", "employee"}
ALIASES_TEMPO |= {"datetime", "dataehora", "datahora", "attendancetime", "punchtime", "time"}
ALIASES_COLUNAS = {"id": ALIASES_ID, "nome": ALIASES_NOME, "tempo": ALIASES_TEMPO}

TEMPO_RE = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}:\d{2})$")


class ErroImportacaoTxtIdTempoMaquina(ValueError):
    """Erro esperado e apresentável durante a leitura deste TXT de relógio."""

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
            raise ErroImportacaoTxtIdTempoMaquina(
                "erro_leitura",
                "Não foi possível ler o arquivo TXT informado.",
            ) from exc
    raise ErroImportacaoTxtIdTempoMaquina(
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
        raise ErroImportacaoTxtIdTempoMaquina("arquivo_vazio", "O arquivo TXT está vazio.")

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

    raise ErroImportacaoTxtIdTempoMaquina(
        "encoding_nao_reconhecido",
        "Não foi possível reconhecer a codificação do arquivo. Use UTF-16 ou UTF-8.",
    )


def _normalizar_nome(valor: Any) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", texto).strip().casefold()


def _normalizar_cabecalho(valor: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _normalizar_nome(valor))


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


def _validar_competencia(mes: int, ano: int) -> None:
    if isinstance(mes, bool) or not isinstance(mes, int) or not 1 <= mes <= 12:
        raise ErroImportacaoTxtIdTempoMaquina("competencia_invalida", "O mês da competência é inválido.")
    if isinstance(ano, bool) or not isinstance(ano, int) or ano < 1:
        raise ErroImportacaoTxtIdTempoMaquina("competencia_invalida", "O ano da competência é inválido.")


def _linhas_txt(conteudo: bytes) -> tuple[list[list[str]], str] | None:
    try:
        texto, encoding = _decodificar(conteudo)
    except ErroImportacaoTxtIdTempoMaquina:
        return None
    if not texto.strip():
        return None
    try:
        leitor = csv.reader(io.StringIO(texto, newline=""), delimiter="\t", strict=True)
        linhas = list(leitor)
    except csv.Error:
        return None
    return linhas, encoding


def _indice_cabecalho(linhas: list[list[str]]) -> int | None:
    return next(
        (indice for indice, linha in enumerate(linhas) if any(celula.strip() for celula in linha)),
        None,
    )


def _indices_colunas_obrigatorias(cabecalho: list[str]) -> dict[str, int] | None:
    indices: dict[str, int] = {}
    for indice, coluna in enumerate(cabecalho):
        normalizada = _normalizar_cabecalho(coluna)
        for papel, aliases in ALIASES_COLUNAS.items():
            if normalizada in aliases:
                indices.setdefault(papel, indice)

    if any(_normalizar_cabecalho(coluna) not in indices for coluna in COLUNAS_OBRIGATORIAS):
        return None
    return indices


def detectar(conteudo: bytes) -> bool:
    """Exige identificador, nome e data/hora, aceitando aliases de cabeçalho."""

    resultado = _linhas_txt(conteudo)
    if resultado is None:
        return False
    linhas, _encoding = resultado

    indice_cabecalho = _indice_cabecalho(linhas)
    if indice_cabecalho is None:
        return False

    if _indices_colunas_obrigatorias(linhas[indice_cabecalho]) is None:
        return False

    # EnNo/Name/DateTime já identifica o layout ISO de txt_log_relogio.
    # Preserva sua prioridade sem criar ambiguidade entre adaptadores específicos.
    return not txt_log_relogio.detectar(conteudo)


def parse_txt_id_tempo_maquina(
    fonte: bytes | bytearray | os.PathLike[str] | str,
    *,
    arquivo_nome: str,
    mes: int,
    ano: int,
    funcionarios: Iterable[Any] = (),
) -> dict[str, Any]:
    """Lê TXT tabulado com ID/Nome/Tempo ou aliases; data/hora mantém formato brasileiro."""

    _validar_competencia(mes, ano)
    dados = _ler_bytes(fonte)
    texto, encoding = _decodificar(dados)
    if not texto.strip():
        raise ErroImportacaoTxtIdTempoMaquina("arquivo_vazio", "O arquivo TXT está vazio.")

    try:
        leitor = csv.reader(io.StringIO(texto, newline=""), delimiter="\t", strict=True)
        linhas = list(leitor)
    except csv.Error as exc:
        raise ErroImportacaoTxtIdTempoMaquina(
            "txt_invalido", "O arquivo TXT possui estrutura inválida."
        ) from exc

    indice_cabecalho = _indice_cabecalho(linhas)
    if indice_cabecalho is None:
        raise ErroImportacaoTxtIdTempoMaquina("arquivo_vazio", "O arquivo TXT está vazio.")

    cabecalho = linhas[indice_cabecalho]
    indices_colunas = _indices_colunas_obrigatorias(cabecalho)
    if indices_colunas is None:
        colunas_normalizadas = {_normalizar_cabecalho(c) for c in cabecalho}
        ausentes = [
            coluna
            for coluna in COLUNAS_OBRIGATORIAS
            if not (ALIASES_COLUNAS[_normalizar_cabecalho(coluna)] & colunas_normalizadas)
        ]
        raise ErroImportacaoTxtIdTempoMaquina(
            "cabecalho_incompativel",
            "Cabeçalho incompatível. Colunas obrigatórias ausentes: " + ", ".join(ausentes) + ".",
        )

    indice_codigo = indices_colunas[_normalizar_cabecalho("ID")]
    indice_nome = indices_colunas[_normalizar_cabecalho("Nome")]
    indice_tempo = indices_colunas[_normalizar_cabecalho("Tempo")]
    maior_indice = max(indice_codigo, indice_nome, indice_tempo)

    grupos: dict[tuple[tuple[str, str], date], dict[str, Any]] = {}
    total_linhas_validas = 0
    for deslocamento, linha in enumerate(linhas[indice_cabecalho + 1 :], start=indice_cabecalho + 2):
        if not any(celula.strip() for celula in linha):
            continue
        if len(linha) <= maior_indice:
            raise ErroImportacaoTxtIdTempoMaquina(
                "linha_invalida",
                f"A linha {deslocamento} não possui todas as colunas obrigatórias.",
            )

        codigo = linha[indice_codigo].strip() or None
        nome = linha[indice_nome].strip()
        tempo_texto = linha[indice_tempo].strip()
        if not nome:
            raise ErroImportacaoTxtIdTempoMaquina(
                "linha_invalida",
                f"O nome do funcionário está vazio na linha {deslocamento}.",
            )

        correspondencia = TEMPO_RE.match(re.sub(r"\s+", " ", tempo_texto))
        if not correspondencia:
            raise ErroImportacaoTxtIdTempoMaquina(
                "tempo_invalido",
                f"Tempo inválido na linha {deslocamento}: {tempo_texto or '(vazio)'}.",
            )

        try:
            data_hora = datetime.strptime(
                f"{correspondencia.group(1)} {correspondencia.group(2)}", "%d/%m/%Y %H:%M:%S"
            )
        except ValueError as exc:
            raise ErroImportacaoTxtIdTempoMaquina(
                "tempo_invalido",
                f"Tempo inválido na linha {deslocamento}: {tempo_texto}.",
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
        raise ErroImportacaoTxtIdTempoMaquina("arquivo_vazio", "O arquivo TXT não contém registros de ponto.")

    por_codigo, por_nome = _indexar_funcionarios(funcionarios)
    nome_arquivo = str(arquivo_nome)
    registros = []
    grupos_ordenados = sorted(
        grupos.values(),
        key=lambda item: (_normalizar_nome(item["nome"]), item["codigo"] or "", item["data"]),
    )

    for grupo in grupos_ordenados:
        batidas = [valor.strftime("%H:%M:%S") for valor in sorted(grupo["batidas"])]
        resultado_interpretacao = interpretar_batidas([batida[:5] for batida in batidas])
        interpretacao = {
            "entrada": resultado_interpretacao["entrada"],
            "saida_intervalo": resultado_interpretacao["saida_almoco"],
            "retorno_intervalo": resultado_interpretacao["retorno_almoco"],
            "saida": resultado_interpretacao["saida"],
        }
        status = "nao_conferido" if resultado_interpretacao["status"] == "normal" else "conferir"
        pendencias = [resultado_interpretacao["observacoes"]] if resultado_interpretacao["observacoes"] else []

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
                "origem": {"tipo": NOME_ADAPTER, "arquivo": nome_arquivo},
            }
        )

    return {
        "encoding": encoding,
        "total_linhas_validas": total_linhas_validas,
        "registros": registros,
    }
