"""Classificação de pendências do dia, sem efeitos persistentes."""
import json

def contar_batidas_originais(valor):
    try:
        batidas = json.loads(valor or "[]")
        return len(batidas) if isinstance(batidas, list) else 0
    except (ValueError, TypeError):
        return 0


def classificar_dia(dia):
    problema = bool(dia.get("pendente_calculo") or dia.get("pendencia_tipo"))
    # Toda batida bruta precisa de destino: um campo ou uma desconsideração justificada.
    # Atribuir só duas de três batidas não resolve a restante. Ocorrência integral
    # decide o dia sem horários; as brutas ficam preservadas apenas como registro.
    preenchidos = sum(bool(dia.get(c)) for c in ("entrada", "saida_almoco", "retorno_almoco", "saida"))
    brutas = dia.get("quantidade_batidas_originais", 0) - dia.get("quantidade_batidas_desconsideradas", 0)
    if brutas > preenchidos and not dia.get("ocorrencia_integral"):
        problema = True
        dia["pendencia_tipo"] = dia.get("pendencia_tipo") or "batidas_nao_atribuidas"
        dia["pendencia_motivo"] = dia.get("pendencia_motivo") if dia.get("pendente_calculo") else (
            "Há batidas originais sem destino. Atribua cada uma a um horário ou desconsidere com justificativa.")
    if dia.get("batida_desconsiderada_em_uso"):
        problema = True
        dia["pendencia_tipo"] = "batida_desconsiderada_em_uso"
        dia["pendencia_motivo"] = "Há batida desconsiderada em uso nos horários. Restaure a batida ou corrija o horário."
    tipo = dia.get("pendencia_tipo")
    rotulos = {"escala_nao_cadastrada": "Sem escala", "escala_incompleta": "Escala incompleta",
        "horario_fixo_incompleto": "Horário incompleto", "batidas_em_dia_sem_calculo": "Conflito de batidas",
        "batidas_nao_atribuidas": "Batida não atribuída",
        "batida_desconsiderada_em_uso": "Batida desconsiderada em uso"}
    rotulo = rotulos.get(tipo, "Conflito")
    if tipo == "batidas_insuficientes":
        rotulo = "Batida ímpar" if (preenchidos % 2 or (not preenchidos and brutas % 2)) else "Batida faltante"
    dia["problema_rotulo"] = rotulo if problema else None
    dia["bloqueante"] = problema
    dia["problema"] = problema
    dia["aguardando_conferencia"] = not problema and not dia["conferido"] and not dia.get("fora_vinculo")
    dia["conferido"] = bool(dia["conferido"] and not problema)
    dia["estado_conferencia"] = "problema" if problema else "conferido" if dia["conferido"] else "aguardando_conferencia"
    # Alias legado representa trabalho restante, não contagem de problemas.
    dia["pendente"] = dia["pendente_operacional"] = problema or dia["aguardando_conferencia"]
    return dia


