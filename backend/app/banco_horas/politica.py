from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException


def hoje_local():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).date()


def validar_prazo(empresa):
    prazo = empresa.prazo_compensacao_banco_horas_dias
    if prazo is None or prazo <= 0:
        raise HTTPException(422, "Configure o prazo de compensação do banco de horas da empresa antes de habilitar o recurso nesta escala.")
    return prazo


def vencimento_credito(data_referencia, prazo):
    try:
        return data_referencia + timedelta(days=prazo)
    except OverflowError as exc:
        raise HTTPException(422, "O prazo informado ultrapassa o limite de datas suportado.") from exc
