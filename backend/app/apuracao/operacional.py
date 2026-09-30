"""Classificação operacional e decisão de fechamento, sem efeitos persistentes."""
import json
from calendar import monthrange
from datetime import date

from app.calendario.service import dentro_vinculo


def classificar_dia(dia):
    problema = bool(dia.get("pendente_calculo") or dia.get("pendencia_tipo"))
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
