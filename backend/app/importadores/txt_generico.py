from __future__ import annotations

import codecs
import csv
import hashlib
import io
import json
import os
import re
import statistics
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from app.importadores.interpretacao_batidas import interpretar_batidas


NOME_ADAPTER = "txt_generico"

# O importador genérico entra apenas como fallback dos layouts específicos.
# A normalização remove acentos, espaços e pontuação antes da comparação.
ALIASES_ID = {
    "id",
    "codigo",
    "cod",
    "matricula",
    "registro",
    "numero",
    "num",
    "n",
    "enno",
    "enrollnumber",
    "enrollno",
    "employeeid",
    "userid",
    "userno",
    "pin",
    "acno",
    "personid",
    "funcionarioid",
}
ALIASES_NOME = {
    "nome",
    "name",
    "funcionario",
    "funcionaria",
    "empregado",
    "empregada",
    "colaborador",
    "colaboradora",
    "employee",
    "employeename",
    "username",
    "personname",
    "nomefuncionario",
}
ALIASES_DATETIME = {
    "datetime",
    "dateandtime",
    "datahora",
    "dataehora",
    "timestamp",
    "checktime",
    "punchdatetime",
    "recordtime",
    "tempo",
    "horario",
    "horarioregistro",
    "horariomarcacao",
    "marcacao",
    "batida",
}
ALIASES_DATA = {
    "data",
    "date",
    "dia",
    "day",
    "recorddate",
    "checkdate",
}
ALIASES_HORA = {
    "hora",
    "time",
    "horario",
    "checktime",
    "recordtime",
    "punch",
    "entrada",
    "saida",
    "entrada1",
    "entrada2",
    "saida1",
    "saida2",
    "inicio",
    "fim",
    "intervalo",
    "saidaintervalo",
    "retornointervalo",
    "saidaalmoco",
    "retornoalmoco",
}

SEPARADORES = ("\t", ";", "|", ",")

FORMATOS_DATA_HORA = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
)
FORMATOS_DATA = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
)
FORMATOS_HORA = ("%H:%M:%S", "%H:%M")

RE_DATA_HORA = re.compile(
    r"(?<!\d)(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4})"
    r"(?:[T\s]+)\d{1,2}:\d{2}(?::\d{2})?(?!\d)"
)
RE_HORA = re.compile(r"(?<!\d)(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?(?!\d)")
RE_DATA = re.compile(
    r"(?<!\d)(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4})(?!\d)"
)


class ErroImportacaoTxtGenerico(ValueError):
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
            raise ErroImportacaoTxtGenerico(
                "erro_leitura", "Não foi possível ler o arquivo TXT informado."
            ) from exc
    raise ErroImportacaoTxtGenerico(
        "fonte_invalida", "A fonte do TXT deve ser conteúdo em bytes ou um caminho de arquivo."
    )


def _parece_utf16_sem_bom(dados: bytes) -> str | None:
    amostra = dados[:4096]
    if len(amostra) < 4:
        return None
    pares = amostra[0::2]
    impares = amostra[1::2]
    if not pares or not impares:
        return None
    nulos_pares = pares.count(0) / len(pares)
    nulos_impares = impares.count(0) / len(impares)
    if nulos_impares >= 0.25 and nulos_impares - nulos_pares >= 0.20:
        return "utf-16-le"
    if nulos_pares >= 0.25 and nulos_pares - nulos_impares >= 0.20:
        return "utf-16-be"
    return None


def _decodificar(dados: bytes) -> tuple[str, str]:
    if not dados:
        raise ErroImportacaoTxtGenerico("arquivo_vazio", "O arquivo TXT está vazio.")

    tentativas: list[tuple[str, str]] = []
    if dados.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        tentativas.append(("utf-16", "utf-16"))
    else:
        utf16 = _parece_utf16_sem_bom(dados)
        if utf16:
            tentativas.append((utf16, utf16))
        if dados.startswith(codecs.BOM_UTF8):
            tentativas.append(("utf-8-sig", "utf-8-sig"))
        tentativas.extend(
            [
                ("utf-8", "utf-8"),
                ("cp1252", "cp1252"),
                ("latin-1", "latin-1"),
                ("gb18030", "gb18030"),
            ]
        )

    vistos: set[str] = set()
    for codec, rotulo in tentativas:
        if codec in vistos:
            continue
        vistos.add(codec)
        try:
            texto = dados.decode(codec, errors="strict")
        except UnicodeError:
            continue
        if "\x00" not in texto:
            return texto, rotulo

    raise ErroImportacaoTxtGenerico(
        "encoding_nao_reconhecido",
        "Não foi possível reconhecer a codificação do TXT.",
    )


def _normalizar_token(valor: Any) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", texto.casefold())


def _normalizar_nome(valor: Any) -> str:
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
        nome = _normalizar_nome(_valor_funcionario(funcionario, "nome"))
        if codigo:
            por_codigo.setdefault(codigo, []).append(funcionario)
        if nome:
            por_nome.setdefault(nome, []).append(funcionario)
    return por_codigo, por_nome


def _localizar_funcionario(
    codigo: str | None,
    nome: str | None,
    por_codigo: dict[str, list[Any]],
    por_nome: dict[str, list[Any]],
) -> Any | None:
    if codigo:
        candidatos = por_codigo.get(codigo, [])
        if len(candidatos) != 1:
            return None
        candidato = candidatos[0]
        if nome and _normalizar_nome(nome) != _normalizar_nome(_valor_funcionario(candidato, "nome")):
            return None
        return candidato
    if nome:
        candidatos = por_nome.get(_normalizar_nome(nome), [])
        if len(candidatos) == 1:
            return candidatos[0]
    return None


def _parse_datetime(valor: str) -> datetime | None:
    texto = re.sub(r"\s+", " ", valor.strip()).replace("T", " ")
    for formato in FORMATOS_DATA_HORA:
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            continue
    return None


def _parse_date(valor: str) -> date | None:
    texto = valor.strip()
    for formato in FORMATOS_DATA:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def _parse_time(valor: str) -> time | None:
    texto = valor.strip()
    for formato in FORMATOS_HORA:
        try:
            return datetime.strptime(texto, formato).time()
        except ValueError:
            continue
    return None


def _pontuar_separador(texto: str, separador: str) -> tuple[int, float, float]:
    amostra_linhas = [linha for linha in texto.splitlines()[:80] if linha.strip()]
    if not amostra_linhas:
        return (0, 0.0, 0.0)
    contagens: list[int] = []
    for linha in amostra_linhas:
        try:
            linha_csv = next(csv.reader([linha], delimiter=separador))
        except (csv.Error, StopIteration):
            continue
        if len(linha_csv) > 1:
            contagens.append(len(linha_csv))
    if len(contagens) < 2:
        return (0, 0.0, 0.0)
    moda = statistics.mode(contagens)
    consistencia = sum(1 for n in contagens if n == moda) / len(contagens)
    return (moda, consistencia, len(contagens) / len(amostra_linhas))


def _escolher_separador(texto: str) -> str | None:
    candidatos = [(sep, _pontuar_separador(texto, sep)) for sep in SEPARADORES]
    candidatos.sort(key=lambda item: item[1], reverse=True)
    melhor_sep, melhor = candidatos[0]
    if melhor[0] >= 2 and melhor[1] >= 0.5 and melhor[2] >= 0.5:
        return melhor_sep
    return None


def _ler_tabela(texto: str, separador: str) -> list[list[str]]:
    try:
        return list(csv.reader(io.StringIO(texto, newline=""), delimiter=separador))
    except csv.Error as exc:
        raise ErroImportacaoTxtGenerico(
            "txt_invalido", "O arquivo TXT possui estrutura tabular inválida."
        ) from exc


def _categoria_cabecalho(valor: str) -> str | None:
    token = _normalizar_token(valor)
    if token in ALIASES_ID:
        return "id"
    if token in ALIASES_NOME:
        return "nome"
    if token in ALIASES_DATETIME:
        return "datetime"
    if token in ALIASES_DATA:
        return "data"
    if token in ALIASES_HORA:
        return "hora"
    if any(chave in token for chave in ("batida", "marcacao", "punch")):
        return "hora"
    if token.startswith("entrada") or token.startswith("saida") or token.startswith("retorno"):
        return "hora"
    return None


def _encontrar_cabecalho(linhas: Sequence[Sequence[str]]) -> tuple[int, dict[str, Any]] | None:
    melhor: tuple[int, int, dict[str, Any]] | None = None
    for indice, linha in enumerate(linhas[:30]):
        if not any(str(celula).strip() for celula in linha):
            continue
        mapa: dict[str, Any] = {"horas": [], "datetimes": []}
        categorias: list[str] = []
        for col, celula in enumerate(linha):
            categoria = _categoria_cabecalho(str(celula))
            if not categoria:
                continue
            categorias.append(categoria)
            if categoria == "hora":
                mapa["horas"].append(col)
            elif categoria == "datetime":
                mapa["datetimes"].append(col)
            else:
                mapa.setdefault(categoria, col)
        if "data" in mapa:
            for col in list(mapa["datetimes"]):
                if _normalizar_token(linha[col]) in ALIASES_HORA:
                    mapa["datetimes"].remove(col)
                    mapa["horas"].append(col)
        tem_identidade = "id" in mapa or "nome" in mapa
        tem_datahora = bool(mapa["datetimes"]) or ("data" in mapa and bool(mapa["horas"]))
        score = len(set(categorias)) + len(mapa["horas"]) + len(mapa["datetimes"])
        if tem_identidade and tem_datahora and (melhor is None or score > melhor[0]):
            melhor = (score, indice, mapa)
    if melhor is None:
        return None
    return melhor[1], melhor[2]


def _ratio(coluna: Sequence[str], parser) -> float:
    valores = [str(v).strip() for v in coluna if str(v).strip()]
    if not valores:
        return 0.0
    return sum(1 for valor in valores if parser(valor) is not None) / len(valores)


def _inferir_layout_sem_cabecalho(linhas: Sequence[Sequence[str]]) -> dict[str, Any] | None:
    dados = [list(linha) for linha in linhas if any(str(c).strip() for c in linha)]
    if len(dados) < 2:
        return None
    largura = max(len(linha) for linha in dados)
    colunas: list[list[str]] = [[] for _ in range(largura)]
    for linha in dados[:100]:
        for indice in range(largura):
            colunas[indice].append(linha[indice] if indice < len(linha) else "")

    dt_scores = [(indice, _ratio(coluna, _parse_datetime)) for indice, coluna in enumerate(colunas)]
    dt_scores = [item for item in dt_scores if item[1] >= 0.65]
    if not dt_scores:
        return None
    indice_datetime = max(dt_scores, key=lambda item: item[1])[0]

    candidatos_identidade = [i for i in range(largura) if i != indice_datetime]
    if not candidatos_identidade:
        return None

    # Nomes tendem a conter letras e espaços; IDs tendem a ser curtos e estáveis.
    def score_nome(indice: int) -> float:
        valores = [str(v).strip() for v in colunas[indice] if str(v).strip()]
        if not valores:
            return 0.0
        return sum(1 for v in valores if any(ch.isalpha() for ch in v)) / len(valores)

    indice_nome = max(candidatos_identidade, key=score_nome)
    nome_score = score_nome(indice_nome)
    outros = [i for i in candidatos_identidade if i != indice_nome]

    mapa: dict[str, Any] = {"datetimes": [indice_datetime], "horas": []}
    if nome_score >= 0.6:
        mapa["nome"] = indice_nome
    if outros:
        def score_id(indice: int) -> float:
            valores = [str(v).strip() for v in colunas[indice] if str(v).strip()]
            if not valores:
                return 0.0
            simples = sum(
                1
                for v in valores
                if len(v) <= 32 and bool(re.fullmatch(r"[A-Za-z0-9_.\-/]+", v))
            )
            return simples / len(valores)

        indice_id = max(outros, key=score_id)
        if score_id(indice_id) >= 0.6:
            mapa["id"] = indice_id

    if "nome" not in mapa and "id" not in mapa:
        return None
    return mapa


def _layout_tabular(texto: str) -> tuple[list[list[str]], int, dict[str, Any], str] | None:
    separador = _escolher_separador(texto)
    if separador is None:
        return None
    linhas = _ler_tabela(texto, separador)
    encontrado = _encontrar_cabecalho(linhas)
    if encontrado:
        indice_cabecalho, mapa = encontrado
        return linhas, indice_cabecalho + 1, mapa, separador
    mapa = _inferir_layout_sem_cabecalho(linhas)
    if mapa:
        return linhas, 0, mapa, separador
    return None


def _parse_linha_livre(linha: str) -> tuple[str | None, str | None, list[datetime]] | None:
    dt_matches = list(RE_DATA_HORA.finditer(linha))
    if not dt_matches:
        return None
    datetimes = [_parse_datetime(match.group(0)) for match in dt_matches]
    datetimes = [valor for valor in datetimes if valor is not None]
    if not datetimes:
        return None

    prefixo = linha[: dt_matches[0].start()].strip(" \t;|,-")
    if not prefixo:
        return None
    partes = re.split(r"[\t;|]+|\s{2,}", prefixo)
    partes = [parte.strip() for parte in partes if parte.strip()]
    if len(partes) == 1:
        correspondencia = re.match(r"^([A-Za-z0-9_.\-/]+)\s+(.+)$", partes[0])
        if correspondencia:
            partes = [correspondencia.group(1), correspondencia.group(2)]

    codigo: str | None = None
    nome: str | None = None
    if len(partes) >= 2:
        codigo = partes[0]
        nome = " ".join(partes[1:])
    elif any(ch.isalpha() for ch in partes[0]):
        nome = partes[0]
    else:
        codigo = partes[0]
    return codigo, nome, datetimes


def _extrair_datetimes_linha(linha: Sequence[str], mapa: Mapping[str, Any]) -> list[datetime]:
    encontrados: list[datetime] = []
    for indice in mapa.get("datetimes", []):
        if indice < len(linha):
            valor = _parse_datetime(str(linha[indice]))
            if valor:
                encontrados.append(valor)

    indice_data = mapa.get("data")
    if indice_data is not None and indice_data < len(linha):
        data_valor = _parse_date(str(linha[indice_data]))
        if data_valor:
            for indice_hora in mapa.get("horas", []):
                if indice_hora < len(linha):
                    hora_valor = _parse_time(str(linha[indice_hora]))
                    if hora_valor:
                        encontrados.append(datetime.combine(data_valor, hora_valor))
    return encontrados


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
        raise ErroImportacaoTxtGenerico("competencia_invalida", "O mês da competência é inválido.")
    if isinstance(ano, bool) or not isinstance(ano, int) or ano < 1:
        raise ErroImportacaoTxtGenerico("competencia_invalida", "O ano da competência é inválido.")


def detectar(conteudo: bytes) -> bool:
    try:
        texto, _encoding = _decodificar(conteudo)
    except ErroImportacaoTxtGenerico:
        return False
    if not texto.strip():
        return False
    if _layout_tabular(texto) is not None:
        return True
    linhas_validas = 0
    for linha in texto.splitlines()[:100]:
        if _parse_linha_livre(linha):
            linhas_validas += 1
            if linhas_validas >= 2:
                return True
    return False


def parse_txt_generico(
    fonte: bytes | bytearray | os.PathLike[str] | str,
    *,
    arquivo_nome: str,
    mes: int,
    ano: int,
    funcionarios: Iterable[Any] = (),
) -> dict[str, Any]:
    """Extrai ID/nome/data/horários de TXT com layout variável e normaliza por dia."""

    _validar_competencia(mes, ano)
    dados = _ler_bytes(fonte)
    texto, encoding = _decodificar(dados)
    if not texto.strip():
        raise ErroImportacaoTxtGenerico("arquivo_vazio", "O arquivo TXT está vazio.")

    grupos: dict[tuple[tuple[str, str], date], dict[str, Any]] = {}
    total_linhas_validas = 0
    total_linhas_ignoradas = 0
    avisos: list[str] = []
    rejeitadas: list[dict] = []

    tabular = _layout_tabular(texto)
    if tabular is not None:
        linhas, inicio_dados, mapa, separador = tabular
        layout_inferido = inicio_dados == 0
        for numero_linha, linha in enumerate(linhas[inicio_dados:], start=inicio_dados + 1):
            if not any(str(celula).strip() for celula in linha):
                continue
            codigo = None
            nome = None
            indice_id = mapa.get("id")
            indice_nome = mapa.get("nome")
            if indice_id is not None and indice_id < len(linha):
                codigo = str(linha[indice_id]).strip() or None
            if indice_nome is not None and indice_nome < len(linha):
                nome = str(linha[indice_nome]).strip() or None
            datetimes = _extrair_datetimes_linha(linha, mapa)
            if not datetimes or (not codigo and not nome):
                total_linhas_ignoradas += 1
                rejeitadas.append({"linha": numero_linha, "conteudo": list(linha), "motivo": "Identificação ou data/hora inválida; confira o arquivo original."})
                continue
            chave_funcionario = ("codigo", codigo) if codigo else ("nome", _normalizar_nome(nome))
            for data_hora in datetimes:
                chave = (chave_funcionario, data_hora.date())
                grupo = grupos.setdefault(
                    chave,
                    {
                        "chave_funcionario": chave_funcionario,
                        "codigo": codigo,
                        "nome": nome,
                        "data": data_hora.date(),
                        "batidas": [],
                        "linhas": [],
                        "nomes": set(),
                        "revisao": [],
                    },
                )
                if nome:
                    grupo["nomes"].add(_normalizar_nome(nome))
                invalidos = [i for i in mapa.get("datetimes", []) if i < len(linha) and str(linha[i]).strip() and not _parse_datetime(str(linha[i]))]
                invalidos += [i for i in mapa.get("horas", []) if i < len(linha) and str(linha[i]).strip() and not _parse_time(str(linha[i]))]
                if invalidos:
                    grupo["revisao"].append(f"Linha {numero_linha}: horário inválido; confira os valores no arquivo original.")
                # Se outra linha trouxer o nome que faltava, aproveita.
                if not grupo["nome"] and nome:
                    grupo["nome"] = nome
                if not grupo["codigo"] and codigo:
                    grupo["codigo"] = codigo
                if nome:
                    grupo["nomes"].add(_normalizar_nome(nome))
                grupo["batidas"].append(data_hora)
                grupo["linhas"].append(numero_linha)
            total_linhas_validas += 1
        formato = f"delimitado:{repr(separador)}"
    else:
        formato = "linhas_livres"
        layout_inferido = True
        for numero_linha, linha in enumerate(texto.splitlines(), start=1):
            if not linha.strip():
                continue
            extraido = _parse_linha_livre(linha)
            if extraido is None:
                total_linhas_ignoradas += 1
                rejeitadas.append({"linha": numero_linha, "conteudo": linha, "motivo": "Linha sem identificação e data/hora interpretáveis."})
                continue
            codigo, nome, datetimes = extraido
            chave_funcionario = ("codigo", codigo) if codigo else ("nome", _normalizar_nome(nome))
            for data_hora in datetimes:
                chave = (chave_funcionario, data_hora.date())
                grupo = grupos.setdefault(
                    chave,
                    {
                        "chave_funcionario": chave_funcionario,
                        "codigo": codigo,
                        "nome": nome,
                        "data": data_hora.date(),
                        "batidas": [],
                        "linhas": [],
                        "nomes": set(),
                        "revisao": [],
                    },
                )
                if nome:
                    grupo["nomes"].add(_normalizar_nome(nome))
                grupo["batidas"].append(data_hora)
                grupo["linhas"].append(numero_linha)
            total_linhas_validas += 1

    if not total_linhas_validas or not grupos:
        raise ErroImportacaoTxtGenerico(
            "formato_nao_interpretavel",
            "Não foi possível localizar ID/nome e data/horário suficientes no TXT.",
        )

    if total_linhas_ignoradas:
        avisos.append(
            f"{total_linhas_ignoradas} linha(s) sem identificação ou horário reconhecível foram ignoradas."
        )

    por_codigo, por_nome = _indexar_funcionarios(funcionarios)
    nome_arquivo = str(arquivo_nome)
    registros: list[dict[str, Any]] = []
    grupos_ordenados = sorted(
        grupos.values(),
        key=lambda item: (_normalizar_nome(item.get("nome")), item.get("codigo") or "", item["data"]),
    )

    for grupo in grupos_ordenados:
        # Mantém ordem e repetições originais; só a interpretação é ordenada.
        batidas_dt = grupo["batidas"]
        batidas = [valor.strftime("%H:%M:%S") for valor in batidas_dt]
        resultado_interpretacao = interpretar_batidas(sorted(batida[:5] for batida in batidas))
        interpretacao = {
            "entrada": resultado_interpretacao["entrada"],
            "saida_intervalo": resultado_interpretacao["saida_almoco"],
            "retorno_intervalo": resultado_interpretacao["retorno_almoco"],
            "saida": resultado_interpretacao["saida"],
        }
        status = "nao_conferido" if resultado_interpretacao["status"] == "normal" else "conferir"
        pendencias = [resultado_interpretacao["observacoes"]] if resultado_interpretacao["observacoes"] else []

        funcionario = _localizar_funcionario(grupo.get("codigo"), grupo.get("nome"), por_codigo, por_nome)
        pendencias.extend(dict.fromkeys(grupo["revisao"]))
        if layout_inferido:
            pendencias.append("Layout sem cabeçalho inferido; confira identificação e horários antes de selecionar.")
        if len(set(batidas)) != len(batidas):
            pendencias.append("Batidas duplicadas preservadas; confira os registros originais.")
            interpretacao = {campo: None for campo in interpretacao}
        if len(grupo["nomes"]) > 1:
            funcionario = None
            pendencias.append("O mesmo ID contém nomes diferentes; associação exige conferência.")
        if pendencias:
            status = "conferir"
        funcionario_id = _valor_funcionario(funcionario, "id") if funcionario is not None else None
        encontrado = funcionario is not None and funcionario_id is not None
        nome_cadastrado = _valor_funcionario(funcionario, "nome") if encontrado else None
        nome_origem = grupo.get("nome") or nome_cadastrado or (f"ID {grupo.get('codigo')}" if grupo.get("codigo") else "")
        fora_da_competencia = grupo["data"].month != mes or grupo["data"].year != ano

        if not encontrado:
            pendencias.append("Funcionário não identificado com segurança; confira ID e nome no cadastro desta empresa")
            status = "conferir"
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
                    "codigo_origem": grupo.get("codigo"),
                    "nome_origem": nome_origem,
                    "nome_cadastrado": nome_cadastrado,
                    "encontrado": encontrado,
                },
                "data": data_iso,
                "batidas_originais": batidas,
                "batidas_normalizadas": sorted(batidas),
                "interpretacao": interpretacao,
                "status": status,
                "pendencias": pendencias,
                "fora_da_competencia": fora_da_competencia,
                "selecionado": encontrado and not fora_da_competencia and not layout_inferido,
                "linhas_origem": sorted(set(grupo["linhas"])),
                "origem": {"tipo": NOME_ADAPTER, "arquivo": nome_arquivo},
            }
        )

    return {
        "encoding": encoding,
        "formato_detectado": formato,
        "total_linhas_validas": total_linhas_validas,
        "total_linhas_ignoradas": total_linhas_ignoradas,
        "avisos": avisos,
        "linhas_rejeitadas": rejeitadas,
        "registros": registros,
    }
