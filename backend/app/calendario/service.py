"""Elegibilidade do vínculo e fonte global de feriados da jornada."""
from datetime import date
import unicodedata

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database.models import Empresa, EventoCalendario, Funcionario


def dentro_periodo(data: date, inicio: date | None, fim: date | None = None) -> bool:
    return (inicio is None or data >= inicio) and (fim is None or data <= fim)


def dentro_vinculo(funcionario: Funcionario, data: date) -> bool:
    return dentro_periodo(data, funcionario.data_admissao, funcionario.data_demissao)


def vinculo_intersecta_periodo(funcionario: Funcionario, inicio: date, fim: date) -> bool:
    return (funcionario.data_admissao is None or funcionario.data_admissao <= fim) and (
        funcionario.data_demissao is None or funcionario.data_demissao >= inicio)


def motivo_fora_vinculo(funcionario: Funcionario, data: date) -> str:
    return "posterior_demissao" if funcionario.data_demissao and data > funcionario.data_demissao else "anterior_admissao"


def data_no_ano(evento: EventoCalendario, ano: int) -> date | None:
    if not evento.recorrente:
        return evento.data if evento.data.year == ano else None
    try:
        return evento.data.replace(year=ano)
    except ValueError:
        # 29/02 não é deslocado artificialmente para outro dia.
        return None


def consultar_eventos(db: Session, ano: int, tipo=None, abrangencia=None):
    consulta = db.query(EventoCalendario).filter(or_(
        EventoCalendario.recorrente.is_(True),
        EventoCalendario.data.between(date(ano, 1, 1), date(ano, 12, 31)),
    ))
    if tipo:
        consulta = consulta.filter(EventoCalendario.tipo == tipo)
    if abrangencia:
        consulta = consulta.filter(EventoCalendario.abrangencia == abrangencia)
    eventos = [e for e in consulta.all() if data_no_ano(e, ano)]
    return sorted(eventos, key=lambda e: (data_no_ano(e, ano), e.nome.casefold(), e.id))


def normalizar_local(valor: str | None) -> str:
    texto = unicodedata.normalize("NFKD", valor or "")
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).casefold().split())


def abrange_empresa(evento: EventoCalendario, empresa: Empresa) -> bool:
    if evento.abrangencia == "NACIONAL":
        return True
    if evento.abrangencia == "EMPRESA":
        return evento.empresa_id == empresa.id
    if not empresa.uf or normalizar_local(evento.uf) != normalizar_local(empresa.uf):
        return False
    if evento.abrangencia == "ESTADUAL":
        return True
    return bool(empresa.cidade and evento.abrangencia == "MUNICIPAL"
                and normalizar_local(evento.municipio) == normalizar_local(empresa.cidade))


def feriados_da_competencia(db: Session, empresa: Empresa, ano: int, mes: int) -> dict[date, list[str]]:
    resultado = {}
    for evento in consultar_eventos(db, ano, tipo="FERIADO"):
        data = data_no_ano(evento, ano)
        if evento.ativo and data.month == mes and abrange_empresa(evento, empresa):
            resultado.setdefault(data, []).append(evento.nome)
    return resultado
