"""Ocorrências são entradas da apuração; nunca modificam batidas ou marcações."""

ROTULOS = {"ATESTADO": "ATESTADO", "DECLARACAO": "DECLARAÇÃO", "FERIAS": "FÉRIAS", "AFASTAMENTO": "AFASTAMENTO", "FOLGA_COMPENSATORIA": "FOLGA COMPENSATÓRIA"}
STATUS_INTEGRAL = {"ATESTADO": "atestado", "FERIAS": "ferias", "AFASTAMENTO": "afastamento", "FOLGA_COMPENSATORIA": "folga_compensatoria"}


def minuto(hora):
    return hora.hour * 60 + hora.minute


def duracao(valor):
    return f"{valor // 60:02d}:{valor % 60:02d}" if valor is not None else None


def intervalos(entrada, saida_almoco, retorno, saida):
    if not entrada or not saida or bool(saida_almoco) != bool(retorno):
        return None
    horas = [h for h in (entrada, saida_almoco, retorno, saida) if h is not None]
    if any(a >= b for a, b in zip(horas, horas[1:])):
        return None
    return [(minuto(horas[i]), minuto(horas[i + 1])) for i in range(0, len(horas), 2)]


def minutos_cobertos(periodos):
    # Precisão por minuto, igual ao motor atual; união evita contagem duplicada.
    return {m for inicio, fim in periodos for m in range(inicio, fim)}


def pendencia(detalhe, motivo):
    detalhe.update(pendente=True, pendente_calculo=True, pendente_operacional=True,
                   pendencia_tipo="ocorrencia_requer_revisao", pendencia_motivo=motivo)


def aplicar_ocorrencias(detalhe, funcionario, marcacao, ocorrencias):
    do_dia = [o for o in ocorrencias if o.data_inicio <= marcacao.data and (o.data_fim is None or o.data_fim >= marcacao.data)]
    detalhe.update(ocorrencias=[{"id": o.id, "tipo": o.tipo, "hora_inicio": o.hora_inicio.isoformat() if o.hora_inicio else None,
                                "hora_fim": o.hora_fim.isoformat() if o.hora_fim else None} for o in do_dia],
                   ocorrencias_rotulo=" / ".join(dict.fromkeys(ROTULOS[o.tipo] for o in do_dia)),
                   minutos_abonados=0, jornada_exigida_minutos=detalhe["jornada_prevista_minutos"])
    if not do_dia:
        return detalhe
    folgas = [o for o in do_dia if o.tipo == "FOLGA_COMPENSATORIA"]
    if folgas:
        detalhe["minutos_folga_compensatoria"] = 0
        if detalhe["jornada_prevista_minutos"] is None:
            pendencia(detalhe, "Folga compensatória exige jornada válida para determinar os minutos utilizados.")
            return detalhe
    integrais = [o for o in do_dia if not o.hora_inicio]
    if integrais:
        if len(do_dia) != 1:
            pendencia(detalhe, "Ocorrências integrais sobrepostas; revise os cadastros.")
            return detalhe
        ocorrencia = integrais[0]
        if ocorrencia.tipo == "FOLGA_COMPENSATORIA":
            detalhe["minutos_folga_compensatoria"] = detalhe["jornada_prevista_minutos"] or 0
        detalhe.update(status_dia=STATUS_INTEGRAL[ocorrencia.tipo], falta=0,
                       atestado=int(ocorrencia.tipo == "ATESTADO"), atraso_minutos=0, atraso="00:00",
                       extra_minutos=0, extra="00:00", jornada_exigida_minutos=0,
                       minutos_abonados=detalhe["jornada_prevista_minutos"] or 0,
                       pendente_calculo=False, pendente=not marcacao.conferido,
                       pendente_operacional=not marcacao.conferido, pendencia_tipo=None,
                       pendencia_motivo=None if marcacao.conferido else "Registro ainda não conferido.")
        if any((marcacao.entrada, marcacao.saida_almoco, marcacao.retorno_almoco, marcacao.saida)):
            pendencia(detalhe, "Há batidas em dia de ocorrência integral. Confira a compatibilidade antes de fechar.")
        return detalhe

    escala = funcionario.escala
    if not escala or escala.modo_apuracao != "horario_fixo":
        pendencia(detalhe, "Abono parcial exige escala com horário fixo; carga horária isolada não define o período exigido.")
        return detalhe
    previstos = intervalos(escala.horario_entrada_prevista, escala.horario_saida_almoco_prevista,
                           escala.horario_retorno_almoco_prevista, escala.horario_saida_prevista)
    realizados = intervalos(marcacao.entrada, marcacao.saida_almoco, marcacao.retorno_almoco, marcacao.saida)
    if previstos is None or realizados is None:
        pendencia(detalhe, "Abono parcial requer horários válidos de escala e batidas completas para evitar suposições.")
        return detalhe
    previstos_set = minutos_cobertos(previstos) if detalhe["jornada_prevista_minutos"] else set()
    trabalhados_set = minutos_cobertos(realizados)
    abonados_set = minutos_cobertos([(minuto(o.hora_inicio), minuto(o.hora_fim)) for o in do_dia])
    ausentes = previstos_set - trabalhados_set
    abono = len(ausentes & abonados_set)
    if folgas:
        detalhe["minutos_folga_compensatoria"] = len(ausentes & minutos_cobertos(
            [(minuto(o.hora_inicio), minuto(o.hora_fim)) for o in folgas]))
    if marcacao.status_dia != "normal":
        pendencia(detalhe, "Ocorrência parcial com situação manual diferente de normal; revise o dia.")
    # Sem ausência coberta, a ocorrência não deve mudar a apuração existente,
    # inclusive as tolerâncias de entrada e intervalo já aplicadas pelo motor.
    if not abono:
        return detalhe
    deficit = len(ausentes - abonados_set)
    if deficit <= escala.tolerancia_atraso_minutos:
        deficit = 0
    if detalhe.get("pendencia_tipo") == "horario_fixo_incompleto":
        # Os intervalos foram reconciliados acima. O atraso anterior era apenas
        # zero por falta de cálculo, não um limite válido para o déficit restante.
        detalhe.update(
            pendente_calculo=False,
            pendente=not marcacao.conferido,
            pendente_operacional=not marcacao.conferido,
            pendencia_tipo=None,
            pendencia_motivo=None if marcacao.conferido else "Registro ainda não conferido.",
        )
    else:
        # Abonar uma ausência nunca pode aumentar o atraso já apurado. Preserva
        # descontos/tolerâncias que o cálculo por interseção não representa.
        deficit = min(deficit, detalhe["atraso_minutos"])
    detalhe.update(minutos_abonados=abono, jornada_exigida_minutos=max((detalhe["jornada_prevista_minutos"] or 0) - abono, 0),
                   atraso_minutos=deficit, atraso=duracao(deficit), falta=0)
    # O abono nunca cria horas trabalhadas nem horas extras.
    return detalhe
