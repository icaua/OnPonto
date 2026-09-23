from __future__ import annotations

from types import ModuleType

from openpyxl.workbook.workbook import Workbook

from app.importadores import (
    txt_generico,
    txt_id_tempo_maquina,
    txt_log_relogio,
    xlsx_cartao_ponto,
    xlsx_ponto_generico,
)


ADAPTADORES_TXT_EXATOS: tuple[ModuleType, ...] = (txt_log_relogio, txt_id_tempo_maquina)
ADAPTADOR_TXT_GENERICO: ModuleType = txt_generico
ADAPTADORES_TXT: tuple[ModuleType, ...] = (*ADAPTADORES_TXT_EXATOS, ADAPTADOR_TXT_GENERICO)
ADAPTADORES_XLSX: tuple[ModuleType, ...] = (xlsx_ponto_generico, xlsx_cartao_ponto)


def detectar_adaptadores_txt(conteudo: bytes) -> list[ModuleType]:
    """Devolve todos os adaptadores TXT registrados que reconhecem a
    estrutura do arquivo. Zero significa formato não reconhecido; mais de um
    significa ambiguidade — em nenhum dos dois casos o chamador deve
    escolher um adaptador por conta própria."""

    # Primeiro preserva os formatos específicos já homologados. O parser genérico
    # só entra quando nenhum deles reconhece o arquivo, evitando ambiguidade.
    encontrados = [adaptador for adaptador in ADAPTADORES_TXT_EXATOS if adaptador.detectar(conteudo)]
    if encontrados:
        return encontrados
    return [ADAPTADOR_TXT_GENERICO] if ADAPTADOR_TXT_GENERICO.detectar(conteudo) else []


def detectar_adaptadores_xlsx(workbook: Workbook) -> list[ModuleType]:
    """Equivalente a detectar_adaptadores_txt, para os adaptadores XLSX."""

    return [adaptador for adaptador in ADAPTADORES_XLSX if adaptador.detectar(workbook)]
