"""Cálculo diário determinístico; adaptadores convertem ORM antes desta fronteira."""
from datetime import date,time
from typing import Any
from app.dominio.contratos import (FuncionarioDoDia,MarcacoesDoDia,RegraVigente,
    ContextoCalendario,OcorrenciasDoDia,ResultadoDia)
from app.dominio.calendario import dentro_vinculo,motivo_fora_vinculo
from app.marcacoes.batidas import desconsideradas_em_uso
from app.dominio.conferencia import contar_batidas_originais,classificar_dia
from app.ocorrencias.interpretacao import aplicar_ocorrencias


STATUS_SEM_CALCULO = {
    "atestado",
    "folga",
    "falta",
    "afastamento",
    "domingo",
    "sem_expediente",
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


def horario_fixo_configurado(funcionario: FuncionarioDoDia) -> bool:
    escala = funcionario.escala
    if not escala or escala.modo_apuracao != "horario_fixo":
        return False
    if not escala.horario_entrada_prevista or not escala.horario_saida_prevista:
        return False
    return bool(escala.horario_saida_almoco_prevista) == bool(
        escala.horario_retorno_almoco_prevista
    )


def jornada_horario_fixo_minutos(escala: RegraVigente) -> int | None:
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


def jornada_prevista_minutos(funcionario: FuncionarioDoDia, data_referencia: date) -> int | None:
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


def tolerancia_intervalo_efetiva(escala: RegraVigente) -> int:
    if escala.tolerancia_intervalo_minutos is not None:
        return escala.tolerancia_intervalo_minutos
    return escala.tolerancia_atraso_minutos


def calcular_atraso_horario_fixo(
    funcionario: FuncionarioDoDia,
    marcacao: MarcacoesDoDia,
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


def calcular_trabalhado(marcacao: MarcacoesDoDia) -> tuple[int, str | None]:
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


def detalhe_marcacao(
    funcionario: FuncionarioDoDia,
    marcacao: MarcacoesDoDia,
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
        if any((marcacao.entrada, marcacao.saida_almoco, marcacao.retorno_almoco, marcacao.saida)) or marcacao.batidas_originais not in (None, "", "[]"):
            pendente_calculo = True
            pendencia_tipo = "batidas_em_dia_sem_calculo"
            motivo_pendencia = "Há batidas em dia sem apuração. Resolva a situação antes de conferir."

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

            if escala.modo_apuracao == "horario_fixo" and (prevista or not escala.politica_horas):
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
        "funcionario": (getattr(funcionario, "nome_exibicao", None) or funcionario.nome),
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
        "quantidade_batidas_originais": contar_batidas_originais(marcacao.batidas_originais),
        "quantidade_batidas_desconsideradas": contar_batidas_originais(marcacao.batidas_desconsideradas_json),
        "batida_desconsiderada_em_uso": desconsideradas_em_uso(marcacao),
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


def detalhe_fora_vinculo(funcionario: FuncionarioDoDia, marcacao: MarcacoesDoDia) -> dict[str, Any]:
    """Preserva o registro para conferência sem executar qualquer regra de jornada."""
    tem_batida = any((marcacao.entrada, marcacao.saida_almoco, marcacao.retorno_almoco, marcacao.saida)) or marcacao.batidas_originais not in (None, "", "[]")
    motivo = motivo_fora_vinculo(funcionario, marcacao.data)
    return {
        "id": marcacao.id, "data": marcacao.data.isoformat(),
        "funcionario_id": funcionario.id, "funcionario": (getattr(funcionario, "nome_exibicao", None) or funcionario.nome),
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


STATUS_AUTOMATICOS_CALENDARIO = {
    ("normal", False),
    ("domingo", True),
    ("sem_expediente", True),
}


def placeholder_calendario_intocado(marcacao: MarcacoesDoDia) -> bool:
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



def apurar_dia(funcionario: FuncionarioDoDia,marcacoes: MarcacoesDoDia,
        calendario: ContextoCalendario=ContextoCalendario(),
        ocorrencias: OcorrenciasDoDia=OcorrenciasDoDia()) -> ResultadoDia:
    dados=detalhe_marcacao(funcionario,marcacoes,{marcacoes.data:list(calendario.feriados)})
    if not dados["fora_vinculo"]:
        aplicar_ocorrencias(dados,funcionario,marcacoes,ocorrencias.itens)
    classificar_dia(dados)
    incompleto=dados["pendente_calculo"] or dados["problema"]
    disponibilidade="indisponivel" if dados["jornada_prevista_minutos"] is None else "incompleto" if incompleto else "completo"
    return ResultadoDia(disponibilidade,
        None if incompleto else dados["horas_trabalhadas_minutos"],dados["jornada_prevista_minutos"],
        None if incompleto else dados["atraso_minutos"],None if incompleto else dados["extra_minutos"],
        dados["pendencia_motivo"],dados)
