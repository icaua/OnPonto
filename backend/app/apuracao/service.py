from calendar import monthrange
import json
from datetime import date, datetime, time
from typing import Any

from sqlalchemy.orm import Session
from app.ocorrencias.service import consultar as consultar_ocorrencias
from app.ocorrencias.interpretacao import aplicar_ocorrencias
from app.banco_horas.service import complementar_apuracao
from app.calendario.service import dentro_vinculo, feriados_da_competencia, motivo_fora_vinculo, vinculo_intersecta_periodo

from app.database.models import (
    ArquivoRecebido,
    Competencia,
    Escala,
    Funcionario,
    MarcacaoPonto,
)


STATUS_SEM_CALCULO = {
    "atestado",
    "folga",
    "falta",
    "afastamento",
    "domingo",
    "sem_expediente",
}
STATUS_AUTOMATICOS_CALENDARIO = {
    ("normal", False),
    ("domingo", True),
    ("sem_expediente", True),
}


def minutos_hora(valor: time) -> int:
    return valor.hour * 60 + valor.minute


def diferenca_minutos(inicio: time, fim: time) -> int | None:
    diferenca = minutos_hora(fim) - minutos_hora(inicio)
    if diferenca < 0:
        return None
    return diferenca


def formatar_minutos(minutos: int | None) -> str | None:
    if minutos is None:
        return None
    sinal = "-" if minutos < 0 else ""
    minutos = abs(minutos)
    horas, resto = divmod(minutos, 60)
    return f"{sinal}{horas:02d}:{resto:02d}"


def formatar_hora(valor: time | None) -> str | None:
    return valor.strftime("%H:%M") if valor else None


def horario_fixo_configurado(funcionario: Funcionario) -> bool:
    escala = funcionario.escala
    if not escala or escala.modo_apuracao != "horario_fixo":
        return False
    if not escala.horario_entrada_prevista or not escala.horario_saida_prevista:
        return False
    return bool(escala.horario_saida_almoco_prevista) == bool(
        escala.horario_retorno_almoco_prevista
    )


def jornada_horario_fixo_minutos(escala: Escala) -> int | None:
    entrada = escala.horario_entrada_prevista
    saida = escala.horario_saida_prevista
    if not entrada or not saida:
        return None

    saida_almoco = escala.horario_saida_almoco_prevista
    retorno_almoco = escala.horario_retorno_almoco_prevista
    if bool(saida_almoco) != bool(retorno_almoco):
        return None
    if saida_almoco and retorno_almoco:
        manha = diferenca_minutos(entrada, saida_almoco)
        tarde = diferenca_minutos(retorno_almoco, saida)
        if manha is None or tarde is None:
            return None
        return manha + tarde
    return diferenca_minutos(entrada, saida)


def jornada_prevista_minutos(funcionario: Funcionario, data_referencia: date) -> int | None:
    escala = funcionario.escala
    if not escala:
        return None

    dia_semana = data_referencia.weekday()
    if dia_semana == 6 and escala.regime_domingo != "trabalha":
        return 0
    if dia_semana == 5 and escala.regime_sabado != "trabalha":
        return 0

    if escala.modo_apuracao == "horario_fixo":
        return jornada_horario_fixo_minutos(escala)

    if escala.modo_apuracao != "carga_horaria":
        return None
    if dia_semana == 5:
        horas = escala.jornada_sabado_horas
    else:
        # A escala atual não possui carga própria de domingo. Quando o domingo é
        # de trabalho, a carga de segunda a sexta é a única referência disponível.
        horas = escala.jornada_seg_sex_horas
    return int(round(horas * 60)) if horas is not None else None


def tolerancia_intervalo_efetiva(escala: Escala) -> int:
    if escala.tolerancia_intervalo_minutos is not None:
        return escala.tolerancia_intervalo_minutos
    return escala.tolerancia_atraso_minutos


def calcular_atraso_horario_fixo(
    funcionario: Funcionario,
    marcacao: MarcacaoPonto,
) -> int | None:
    if not horario_fixo_configurado(funcionario) or not marcacao.entrada:
        return None

    escala = funcionario.escala
    if escala is None or escala.horario_entrada_prevista is None:
        return None

    atraso_entrada = max(
        minutos_hora(marcacao.entrada) - minutos_hora(escala.horario_entrada_prevista),
        0,
    )
    if atraso_entrada <= escala.tolerancia_atraso_minutos:
        atraso_entrada = 0

    excesso_intervalo = 0
    if escala.horario_saida_almoco_prevista and escala.horario_retorno_almoco_prevista:
        if not marcacao.saida_almoco or not marcacao.retorno_almoco:
            return None
        intervalo_previsto = diferenca_minutos(
            escala.horario_saida_almoco_prevista,
            escala.horario_retorno_almoco_prevista,
        )
        intervalo_realizado = diferenca_minutos(
            marcacao.saida_almoco,
            marcacao.retorno_almoco,
        )
        if intervalo_previsto is None or intervalo_realizado is None:
            return None
        excesso_intervalo = max(intervalo_realizado - intervalo_previsto, 0)
        if excesso_intervalo <= tolerancia_intervalo_efetiva(escala):
            excesso_intervalo = 0

    return atraso_entrada + excesso_intervalo


def calcular_trabalhado(marcacao: MarcacaoPonto) -> tuple[int, str | None]:
    if not marcacao.entrada or not marcacao.saida:
        return 0, "Entrada ou saída não informada."

    if bool(marcacao.saida_almoco) != bool(marcacao.retorno_almoco):
        return 0, "Intervalo de almoço incompleto."

    horarios = [h for h in (marcacao.entrada, marcacao.saida_almoco, marcacao.retorno_almoco, marcacao.saida) if h is not None]
    if any(a >= b for a, b in zip(horarios, horarios[1:])):
        return 0, "Sequência de horários inválida."

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


def configuracao_calendario(funcionario: Funcionario, data_referencia: date) -> tuple[str, bool]:
    escala = funcionario.escala
    if not escala:
        return "normal", False

    dia_semana = data_referencia.weekday()
    if dia_semana == 6:
        if escala.regime_domingo == "nao_trabalha":
            return "domingo", True
        return "normal", False
    if dia_semana == 5:
        if escala.regime_sabado in {"compensado", "nao_trabalha"}:
            return "sem_expediente", True
        return "normal", False
    return "normal", False


def placeholder_calendario_intocado(marcacao: MarcacaoPonto) -> bool:
    """Identifica somente dias automáticos que ainda não receberam decisão humana."""

    return (
        marcacao.origem == "calendario"
        and marcacao.arquivo_origem_id is None
        and marcacao.batidas_originais in (None, "", "[]")
        and marcacao.observacoes in (None, "")
        and marcacao.historico_json in (None, "", "[]")
        and (marcacao.status_dia, bool(marcacao.conferido))
        in STATUS_AUTOMATICOS_CALENDARIO
        and all(
            valor is None
            for valor in (
                marcacao.entrada,
                marcacao.saida_almoco,
                marcacao.retorno_almoco,
                marcacao.saida,
            )
        )
    )


def gerar_dias_faltantes(db: Session, competencia: Competencia) -> int:
    """Gera o calendário no primeiro processamento da competência, sem commit.

    O helper só faz ``flush`` para participar da transação do chamador. Isso mantém
    idempotentes chamadas repetidas na mesma sessão e deixa a fronteira de commit
    na apuração, nos relatórios e nas ações de fechamento/reabertura que o chamam.
    """

    if competencia.status == "fechada":
        return 0
    db.flush()
    funcionarios = (
        db.query(Funcionario)
        .filter(
            Funcionario.empresa_id == competencia.empresa_id,
            Funcionario.ativo.is_(True),
        )
        .all()
    )
    if not funcionarios:
        return 0

    existentes = {
        (marcacao.funcionario_id, marcacao.data): marcacao
        for marcacao in (
            db.query(MarcacaoPonto)
            .filter(MarcacaoPonto.competencia_id == competencia.id)
            .all()
        )
    }
    ultimo_dia = monthrange(competencia.ano, competencia.mes)[1]
    criadas = 0
    for funcionario in funcionarios:
        for dia in range(1, ultimo_dia + 1):
            data_marcacao = date(competencia.ano, competencia.mes, dia)
            chave = (funcionario.id, data_marcacao)
            existente = existentes.get(chave)
            if not dentro_vinculo(funcionario, data_marcacao):
                if existente is not None and placeholder_calendario_intocado(existente):
                    db.delete(existente)
                continue
            if existente is not None:
                # Um placeholder automático acompanha mudanças posteriores da
                # escala. Marcações importadas ou já tocadas pelo usuário nunca
                # são reinterpretadas aqui.
                if placeholder_calendario_intocado(existente):
                    status_dia, conferido = configuracao_calendario(
                        funcionario,
                        data_marcacao,
                    )
                    existente.status_dia = status_dia
                    existente.conferido = conferido
                continue
            status_dia, conferido = configuracao_calendario(funcionario, data_marcacao)
            nova_marcacao = MarcacaoPonto(
                competencia_id=competencia.id,
                funcionario_id=funcionario.id,
                data=data_marcacao,
                status_dia=status_dia,
                origem="calendario",
                conferido=conferido,
            )
            db.add(nova_marcacao)
            existentes[chave] = nova_marcacao
            criadas += 1

    db.flush()
    return criadas


def detalhe_marcacao(
    funcionario: Funcionario,
    marcacao: MarcacaoPonto,
    feriados: dict | None = None,
) -> dict[str, Any]:
    if not dentro_vinculo(funcionario, marcacao.data):
        return detalhe_fora_vinculo(funcionario, marcacao)
    nomes_feriados = (feriados or {}).get(marcacao.data, [])
    feriado_aplicado = bool(nomes_feriados and marcacao.status_dia in {"normal", "domingo", "sem_expediente"})
    status_dia = "feriado" if feriado_aplicado else marcacao.status_dia
    conferido = marcacao.conferido or (feriado_aplicado and placeholder_calendario_intocado(marcacao))
    escala = funcionario.escala
    prevista = jornada_prevista_minutos(funcionario, marcacao.data)
    trabalhadas = 0
    atraso = 0
    extra = 0
    horas_feriado = 0
    horas_feriado_pendente = False
    pendente_calculo = False
    pendencia_tipo = None
    motivo_pendencia = None

    if status_dia == "feriado":
        prevista = 0
    elif not escala:
        pendente_calculo = True
        pendencia_tipo = "escala_nao_cadastrada"
        motivo_pendencia = "Escala não cadastrada para o funcionário."
    elif prevista is None:
        pendente_calculo = True
        pendencia_tipo = "escala_incompleta"
        motivo_pendencia = "A escala não possui dados suficientes para apurar o dia."

    if status_dia == "falta":
        falta = 1
        atestado = 0
    elif status_dia == "atestado":
        falta = 0
        atestado = 1
    else:
        falta = 0
        atestado = 0

    if status_dia == "feriado":
        tem_batida = any((marcacao.entrada, marcacao.saida_almoco, marcacao.retorno_almoco, marcacao.saida)) or marcacao.batidas_originais not in (None, "", "[]")
        if tem_batida:
            trabalhadas, motivo_batidas = calcular_trabalhado(marcacao)
            if motivo_batidas:
                pendente_calculo = True
                horas_feriado_pendente = True
                pendencia_tipo = "batidas_insuficientes"
                motivo_pendencia = "Batidas de feriado requerem revisão: " + motivo_batidas
            else:
                horas_feriado = trabalhadas
        else:
            # Ausência de trabalho é esperada no feriado, inclusive sem escala.
            conferido = True
    elif status_dia in STATUS_SEM_CALCULO:
        trabalhadas = 0
    else:
        trabalhadas, motivo_batidas = calcular_trabalhado(marcacao)
        if motivo_batidas is not None and motivo_pendencia is None:
            motivo_pendencia = motivo_batidas
            pendencia_tipo = "batidas_insuficientes"
        pendente_calculo = pendente_calculo or motivo_batidas is not None

        if not pendente_calculo and prevista is not None and escala is not None:
            deficit_carga = max(prevista - trabalhadas, 0)
            if deficit_carga <= escala.tolerancia_atraso_minutos:
                deficit_carga = 0

            if escala.modo_apuracao == "horario_fixo":
                atraso_horario = calcular_atraso_horario_fixo(funcionario, marcacao)
                if atraso_horario is None:
                    pendente_calculo = True
                    pendencia_tipo = "horario_fixo_incompleto"
                    motivo_pendencia = "As batidas não permitem conferir o horário fixo."
                else:
                    atraso = max(deficit_carga, atraso_horario)
            else:
                atraso = deficit_carga

            if not pendente_calculo and trabalhadas > prevista:
                extra = trabalhadas - prevista
                if extra <= escala.tolerancia_extra_minutos:
                    extra = 0

    pendente_operacional = pendente_calculo or not conferido
    if motivo_pendencia:
        pendencia_motivo = motivo_pendencia
    elif not conferido:
        pendencia_motivo = "Registro ainda não conferido."
    else:
        pendencia_motivo = None

    return {
        "id": marcacao.id,
        "data": marcacao.data.isoformat(),
        "funcionario_id": funcionario.id,
        "funcionario": funcionario.nome,
        "entrada": formatar_hora(marcacao.entrada),
        "saida_almoco": formatar_hora(marcacao.saida_almoco),
        "retorno_almoco": formatar_hora(marcacao.retorno_almoco),
        "saida": formatar_hora(marcacao.saida),
        "status_dia": status_dia,
        "status_original": marcacao.status_dia,
        "feriados": nomes_feriados,
        "feriado_aplicado": feriado_aplicado,
        "fora_vinculo": False,
        "origem": marcacao.origem,
        "conferido": conferido,
        "jornada_prevista_minutos": prevista,
        "jornada_prevista": formatar_minutos(prevista),
        "horas_trabalhadas_minutos": trabalhadas,
        "horas_trabalhadas": formatar_minutos(trabalhadas),
        "horas_feriado_minutos": horas_feriado,
        "horas_feriado": formatar_minutos(horas_feriado),
        "horas_feriado_pendente": horas_feriado_pendente,
        "atraso_minutos": atraso,
        "atraso": formatar_minutos(atraso),
        "extra_minutos": extra,
        "extra": formatar_minutos(extra),
        "falta": falta,
        "atestado": atestado,
        "pendente": pendente_operacional,
        "pendente_calculo": pendente_calculo,
        "pendente_operacional": pendente_operacional,
        "pendencia_tipo": pendencia_tipo,
        "pendencia_motivo": pendencia_motivo,
        "observacoes": marcacao.observacoes,
    }


def detalhe_fora_vinculo(funcionario: Funcionario, marcacao: MarcacaoPonto) -> dict[str, Any]:
    """Preserva o registro para conferência sem executar qualquer regra de jornada."""
    tem_batida = any((marcacao.entrada, marcacao.saida_almoco, marcacao.retorno_almoco, marcacao.saida)) or marcacao.batidas_originais not in (None, "", "[]")
    motivo = motivo_fora_vinculo(funcionario, marcacao.data)
    return {
        "id": marcacao.id, "data": marcacao.data.isoformat(),
        "funcionario_id": funcionario.id, "funcionario": funcionario.nome,
        **{campo: formatar_hora(getattr(marcacao, campo)) for campo in ("entrada", "saida_almoco", "retorno_almoco", "saida")},
        "status_dia": "fora_vinculo", "status_original": marcacao.status_dia,
        "origem": marcacao.origem, "conferido": marcacao.conferido,
        "fora_vinculo": True, "feriados": [], "feriado_aplicado": False,
        "jornada_prevista_minutos": 0, "jornada_prevista": "00:00",
        "jornada_exigida_minutos": 0, "horas_trabalhadas_minutos": 0, "horas_trabalhadas": "00:00",
        "horas_feriado_minutos": 0, "horas_feriado": "00:00", "horas_feriado_pendente": False,
        "atraso_minutos": 0, "atraso": "00:00", "extra_minutos": 0, "extra": "00:00",
        "falta": 0, "atestado": 0, "minutos_abonados": 0, "ocorrencias": [], "ocorrencias_rotulo": "",
        "pendente": bool(tem_batida), "pendente_operacional": bool(tem_batida), "pendente_calculo": False,
        "pendencia_tipo": "marcacao_" + motivo if tem_batida else None,
        "pendencia_motivo": ("Marcação posterior à data de demissão" if motivo == "posterior_demissao" else "Marcação anterior à data de admissão") if tem_batida else None,
        "observacoes": marcacao.observacoes,
    }


def apurar_competencia(
    db: Session,
    competencia_id: int,
    *,
    gerar_calendario: bool = True,
    incluir_banco: bool = True,
) -> dict[str, Any] | None:
    competencia = db.get(Competencia, competencia_id)
    if not competencia:
        return None

    if competencia.status == "fechada":
        if competencia.apuracao_fechada:
            resultado = json.loads(competencia.apuracao_fechada)
            return complementar_apuracao(db, competencia, resultado) if incluir_banco else resultado
        gerar_calendario = False

    if gerar_calendario:
        gerar_dias_faltantes(db, competencia)

    empresa = competencia.empresa
    feriados = feriados_da_competencia(db, empresa, competencia.ano, competencia.mes)
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
            "dias_processados": 0,
            "atrasos_minutos": 0,
            "extras_minutos": 0,
            "atrasos": "00:00",
            "extras": "00:00",
            "horas_feriado_minutos": 0,
            "horas_feriado": "00:00",
            "_horas_feriado_pendentes": False,
            "faltas": 0,
            "atestados": 0,
            "pendencias": 0,
            "situacao": "indisponivel",
            "observacoes": "",
            "_duracoes_disponiveis": True,
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
    dias_com_pendencia: set[tuple[int, date]] = set()
    ocorrencias_por_funcionario = {}
    for ocorrencia in consultar_ocorrencias(db, empresa_id=competencia.empresa_id,
            inicio=date(competencia.ano, competencia.mes, 1),
            fim=date(competencia.ano, competencia.mes, monthrange(competencia.ano, competencia.mes)[1])):
        ocorrencias_por_funcionario.setdefault(ocorrencia.funcionario_id, []).append(ocorrencia)

    for marcacao in marcacoes:
        funcionario = funcionarios_por_id.get(marcacao.funcionario_id)
        if not funcionario:
            continue

        if not dentro_vinculo(funcionario, marcacao.data) and placeholder_calendario_intocado(marcacao):
            continue
        detalhe = detalhe_marcacao(funcionario, marcacao, feriados)
        if not detalhe["fora_vinculo"]:
            aplicar_ocorrencias(detalhe, funcionario, marcacao, ocorrencias_por_funcionario.get(funcionario.id, []))
        detalhes.append(detalhe)

        item_resumo = resumo[funcionario.id]
        item_resumo["dias_processados"] += int(not detalhe["fora_vinculo"])
        item_resumo["atrasos_minutos"] += detalhe["atraso_minutos"]
        item_resumo["extras_minutos"] += detalhe["extra_minutos"]
        item_resumo["horas_feriado_minutos"] += detalhe["horas_feriado_minutos"]
        item_resumo["_horas_feriado_pendentes"] |= detalhe["horas_feriado_pendente"]
        item_resumo["faltas"] += detalhe["falta"]
        item_resumo["atestados"] += detalhe["atestado"]
        if detalhe["pendente_calculo"]:
            item_resumo["_duracoes_disponiveis"] = False
        if detalhe["pendente"]:
            item_resumo["pendencias"] += 1
            pendencias.append(detalhe)
            dias_com_pendencia.add((funcionario.id, marcacao.data))

    for item in resumo.values():
        if item.pop("_horas_feriado_pendentes"):
            item["horas_feriado_minutos"] = None
        item["horas_feriado"] = formatar_minutos(item["horas_feriado_minutos"])
        motivos_vinculo = {d["pendencia_tipo"] for d in pendencias if d["funcionario_id"] == item["funcionario_id"] and d.get("fora_vinculo")}
        if motivos_vinculo:
            item["observacoes"] = "; ".join(texto for tipo, texto in [
                ("marcacao_anterior_admissao", "Existem marcações anteriores à admissão"),
                ("marcacao_posterior_demissao", "Existem marcações posteriores à demissão"),
            ] if tipo in motivos_vinculo)
        fora_competencia = not vinculo_intersecta_periodo(funcionarios_por_id[item["funcionario_id"]],
            date(competencia.ano, competencia.mes, 1),
            date(competencia.ano, competencia.mes, monthrange(competencia.ano, competencia.mes)[1]))
        if item["dias_processados"] == 0 and (fora_competencia or item["pendencias"]):
            item["situacao"] = "pendente" if item["pendencias"] else "fora_vinculo"
            if not item["observacoes"]:
                item["observacoes"] = "Fora do vínculo nesta competência"
        elif item["dias_processados"] == 0:
            item["atrasos_minutos"] = None
            item["extras_minutos"] = None
            item["atrasos"] = None
            item["extras"] = None
            item["faltas"] = None
            item["atestados"] = None
            item["pendencias"] = None
            item["situacao"] = "indisponivel"
        else:
            if item["_duracoes_disponiveis"]:
                item["atrasos"] = formatar_minutos(item["atrasos_minutos"])
                item["extras"] = formatar_minutos(item["extras_minutos"])
            else:
                item["atrasos_minutos"] = None
                item["extras_minutos"] = None
                item["atrasos"] = None
                item["extras"] = None
            item["situacao"] = "pendente" if item["pendencias"] else "conferido"
        del item["_duracoes_disponiveis"]

    resumo_funcionarios = list(resumo.values())
    resumo_geral = {
        "funcionarios": len(resumo_funcionarios),
        "conferidos": sum(1 for item in resumo_funcionarios if item["situacao"] == "conferido"),
        "pendentes": sum(1 for item in resumo_funcionarios if item["situacao"] == "pendente"),
        "dias_com_pendencia": len(dias_com_pendencia),
        "total_arquivos": (
            db.query(ArquivoRecebido)
            .filter(ArquivoRecebido.competencia_id == competencia.id)
            .count()
        ),
    }

    if gerar_calendario and competencia.status != "fechada":
        if not marcacoes:
            competencia.status = "aberta"
        else:
            competencia.status = "em_conferencia" if pendencias else "conferida"

    resultado = {
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
        "resumo_geral": resumo_geral,
        "resumo": resumo_funcionarios,
        "marcacoes": detalhes,
        "pendencias": pendencias,
    }
    return complementar_apuracao(db, competencia, resultado) if incluir_banco else resultado
