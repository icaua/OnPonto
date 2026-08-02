from datetime import date, datetime, time
from typing import Any

from sqlalchemy.orm import Session

from app.database.models import Competencia, Empresa, Funcionario, MarcacaoPonto


def minutos_hora(valor: time) -> int:
    return valor.hour * 60 + valor.minute


def diferenca_minutos(inicio: time, fim: time) -> int | None:
    diferenca = minutos_hora(fim) - minutos_hora(inicio)
    if diferenca < 0:
        return None
    return diferenca


def formatar_minutos(minutos: int) -> str:
    sinal = "-" if minutos < 0 else ""
    minutos = abs(minutos)
    horas, resto = divmod(minutos, 60)
    return f"{sinal}{horas:02d}:{resto:02d}"


def formatar_hora(valor: time | None) -> str | None:
    return valor.strftime("%H:%M") if valor else None


def jornada_prevista_minutos(empresa: Empresa, funcionario: Funcionario, data: date) -> int:
    dia_semana = data.weekday()
    if dia_semana <= 4:
        horas = funcionario.jornada_especifica_seg_sex_horas
        if horas is None:
            horas = empresa.jornada_seg_sex_horas
        return int(round(horas * 60))
    if dia_semana == 5:
        horas = funcionario.jornada_especifica_sabado_horas
        if horas is None:
            horas = empresa.jornada_sabado_horas
        return int(round(horas * 60))
    return 0


def calcular_trabalhado(marcacao: MarcacaoPonto) -> tuple[int, str | None]:
    if not marcacao.entrada or not marcacao.saida:
        return 0, "Entrada ou saída não informada."

    if bool(marcacao.saida_almoco) != bool(marcacao.retorno_almoco):
        return 0, "Intervalo de almoço incompleto."

    if marcacao.saida_almoco and marcacao.retorno_almoco:
        manha = diferenca_minutos(marcacao.entrada, marcacao.saida_almoco)
        tarde = diferenca_minutos(marcacao.retorno_almoco, marcacao.saida)
        if manha is None or tarde is None:
            return 0, "Sequência de horários inválida."
        return manha + tarde, None

    total = diferenca_minutos(marcacao.entrada, marcacao.saida)
    if total is None:
        return 0, "Sequência de horários inválida."
    return total, None


def detalhe_marcacao(
    empresa: Empresa,
    funcionario: Funcionario,
    marcacao: MarcacaoPonto,
) -> dict[str, Any]:
    prevista = jornada_prevista_minutos(empresa, funcionario, marcacao.data)
    trabalhadas = 0
    atraso = 0
    extra = 0
    pendente = False
    motivo_pendencia = None

    if marcacao.status_dia == "falta":
        falta = 1
        atestado = 0
    elif marcacao.status_dia == "atestado":
        falta = 0
        atestado = 1
    else:
        falta = 0
        atestado = 0

    if marcacao.status_dia in {"atestado", "folga", "feriado", "falta"}:
        trabalhadas = 0
    else:
        trabalhadas, motivo_pendencia = calcular_trabalhado(marcacao)
        pendente = marcacao.status_dia in {"pendente", "pendente_conferencia"} or motivo_pendencia is not None

        if not pendente:
            if trabalhadas < prevista:
                atraso = prevista - trabalhadas
                if atraso <= empresa.tolerancia_atraso_minutos:
                    atraso = 0
            elif trabalhadas > prevista:
                extra = trabalhadas - prevista
                if extra <= empresa.tolerancia_extra_minutos:
                    extra = 0

    return {
        "id": marcacao.id,
        "data": marcacao.data.isoformat(),
        "funcionario_id": funcionario.id,
        "funcionario": funcionario.nome,
        "entrada": formatar_hora(marcacao.entrada),
        "saida_almoco": formatar_hora(marcacao.saida_almoco),
        "retorno_almoco": formatar_hora(marcacao.retorno_almoco),
        "saida": formatar_hora(marcacao.saida),
        "status_dia": marcacao.status_dia,
        "origem": marcacao.origem,
        "conferido": marcacao.conferido,
        "jornada_prevista_minutos": prevista,
        "jornada_prevista": formatar_minutos(prevista),
        "horas_trabalhadas_minutos": trabalhadas,
        "horas_trabalhadas": formatar_minutos(trabalhadas),
        "atraso_minutos": atraso,
        "atraso": formatar_minutos(atraso),
        "extra_minutos": extra,
        "extra": formatar_minutos(extra),
        "falta": falta,
        "atestado": atestado,
        "pendente": pendente,
        "pendencia_motivo": motivo_pendencia or ("Dia pendente." if marcacao.status_dia in {"pendente", "pendente_conferencia"} else None),
        "observacoes": marcacao.observacoes,
    }


def apurar_competencia(db: Session, competencia_id: int) -> dict[str, Any] | None:
    competencia = db.get(Competencia, competencia_id)
    if not competencia:
        return None

    empresa = competencia.empresa
    funcionarios = (
        db.query(Funcionario)
        .filter(Funcionario.empresa_id == competencia.empresa_id)
        .order_by(Funcionario.nome.asc())
        .all()
    )
    funcionarios_por_id = {funcionario.id: funcionario for funcionario in funcionarios}

    resumo = {
        funcionario.id: {
            "funcionario_id": funcionario.id,
            "funcionario": funcionario.nome,
            "codigo": funcionario.codigo,
            "atrasos_minutos": 0,
            "extras_minutos": 0,
            "atrasos": "00:00",
            "extras": "00:00",
            "faltas": 0,
            "atestados": 0,
            "pendencias": 0,
            "observacoes": "",
        }
        for funcionario in funcionarios
    }

    marcacoes = (
        db.query(MarcacaoPonto)
        .filter(MarcacaoPonto.competencia_id == competencia.id)
        .order_by(MarcacaoPonto.data.asc(), MarcacaoPonto.funcionario_id.asc())
        .all()
    )

    detalhes = []
    pendencias = []

    for marcacao in marcacoes:
        funcionario = funcionarios_por_id.get(marcacao.funcionario_id)
        if not funcionario:
            continue

        detalhe = detalhe_marcacao(empresa, funcionario, marcacao)
        detalhes.append(detalhe)

        item_resumo = resumo[funcionario.id]
        item_resumo["atrasos_minutos"] += detalhe["atraso_minutos"]
        item_resumo["extras_minutos"] += detalhe["extra_minutos"]
        item_resumo["faltas"] += detalhe["falta"]
        item_resumo["atestados"] += detalhe["atestado"]
        if detalhe["pendente"]:
            item_resumo["pendencias"] += 1
            pendencias.append(detalhe)

    for item in resumo.values():
        item["atrasos"] = formatar_minutos(item["atrasos_minutos"])
        item["extras"] = formatar_minutos(item["extras_minutos"])

    return {
        "empresa": {
            "id": empresa.id,
            "nome": empresa.nome,
            "cnpj": empresa.cnpj,
        },
        "competencia": {
            "id": competencia.id,
            "mes": competencia.mes,
            "ano": competencia.ano,
            "label": f"{competencia.mes:02d}/{competencia.ano}",
            "status": competencia.status,
        },
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "resumo": list(resumo.values()),
        "marcacoes": detalhes,
        "pendencias": pendencias,
    }
