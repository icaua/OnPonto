"""Classificação operacional e decisão de fechamento, sem efeitos persistentes."""
import json
from calendar import monthrange
from datetime import date

from app.calendario.service import dentro_vinculo


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
    if brutas > preenchidos and preenchidos < 4 and not dia.get("ocorrencia_integral"):
        problema = True
        dia["pendencia_tipo"] = dia.get("pendencia_tipo") or "batidas_nao_atribuidas"
        dia["pendencia_motivo"] = dia.get("pendencia_motivo") if dia.get("pendente_calculo") else (
            "Há batidas originais sem destino. Atribua cada uma a um horário ou desconsidere com justificativa.")
    tipo = dia.get("pendencia_tipo")
    rotulos = {"escala_nao_cadastrada": "Sem escala", "escala_incompleta": "Escala incompleta",
        "horario_fixo_incompleto": "Horário incompleto", "batidas_em_dia_sem_calculo": "Conflito de batidas",
        "batidas_nao_atribuidas": "Batida não atribuída"}
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


def controle_arquivo(arquivo):
    return json.loads(arquivo.controle_importacao_json) if arquivo.controle_importacao_json else None


def indicadores(resultado, funcionarios, arquivos, competencia):
    dias = resultado["marcacoes"]
    controles = [controle_arquivo(a) for a in arquivos]
    pendencias_importacao = [dict(p, arquivo_id=a.id) for a, c in zip(arquivos, controles) if c for p in c.get("pendencias", [])]
    analises = sum(1 for a, c in zip(arquivos, controles) if (c and c.get("estado") != "confirmada") or (not c and not a.marcacoes))
    presentes = {(d["funcionario_id"], d["data"]) for d in dias}
    faltantes = sum(1 for f in funcionarios if f.ativo for n in range(1, monthrange(competencia.ano, competencia.mes)[1] + 1)
        if dentro_vinculo(f, date(competencia.ano, competencia.mes, n)) and (f.id, date(competencia.ano, competencia.mes, n).isoformat()) not in presentes)
    contagens = {"problemas": sum(d["problema"] for d in dias),
        "aguardando_conferencia": sum(d["aguardando_conferencia"] for d in dias),
        "conferidos": sum(d["conferido"] for d in dias), "total": len(dias),
        "dias_sem_registro": faltantes, "analises_pendentes": analises,
        "conflitos_importacao": len(pendencias_importacao), "total_arquivos": len(arquivos)}
    motivos = []
    if not dias: motivos.append("Não há registros processados.")
    if analises: motivos.append(f"{analises} arquivo(s) aguardam confirmação da importação.")
    if pendencias_importacao: motivos.append(f"{len(pendencias_importacao)} registro(s) de importação não resolvidos.")
    if contagens["problemas"]: motivos.append(f"{contagens['problemas']} dia(s) com problemas bloqueantes.")
    if contagens["aguardando_conferencia"]: motivos.append(f"{contagens['aguardando_conferencia']} dia(s) aguardam conferência.")
    if faltantes: motivos.append(f"{faltantes} dia(s) do vínculo sem registro. Inicialize o calendário ou confirme a importação.")
    fechada = competencia.status == "fechada"
    proxima = ("exportar" if fechada else "confirmar_importacao" if analises else
        "resolver_problemas" if contagens["problemas"] or pendencias_importacao else
        "importar" if not dias else "continuar_conferencia" if contagens["aguardando_conferencia"] or faltantes else "revisar_fechar")
    resultado["operacional"] = contagens
    resultado["pendencias_importacao"] = pendencias_importacao
    resultado["fechamento"] = {"pode_fechar": not fechada and not motivos,
        "motivo_bloqueio": "A competência já está fechada." if fechada else " ".join(motivos) or None,
        "motivos": motivos, "proxima_acao": proxima}
    return resultado
