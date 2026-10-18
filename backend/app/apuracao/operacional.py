"""Classificação operacional e decisão de fechamento, sem efeitos persistentes."""
import json
from calendar import monthrange
from datetime import date

from app.calendario.service import dentro_vinculo, vinculo_intersecta_periodo, vinculo_permite_calendario


from app.dominio.conferencia import contar_batidas_originais,classificar_dia


def controle_arquivo(arquivo):
    return json.loads(arquivo.controle_importacao_json) if arquivo.controle_importacao_json else None


def indicadores(resultado, funcionarios, arquivos, competencia, *, arquivos_com_marcacoes=None, contagens_dias=None, presentes=None):
    dias = resultado["marcacoes"]
    controles = [controle_arquivo(a) for a in arquivos]
    pendencias_importacao = [dict(p, arquivo_id=a.id) for a, c in zip(arquivos, controles) if c for p in c.get("pendencias", [])]
    analises = sum(1 for a, c in zip(arquivos, controles) if (c and c.get("estado") != "confirmada") or
        (not c and (a.id not in arquivos_com_marcacoes if arquivos_com_marcacoes is not None else not a.marcacoes)))
    if presentes is None: presentes = {(d["funcionario_id"], d["data"]) for d in dias}
    inicio = date(competencia.ano, competencia.mes, 1)
    fim = date(competencia.ano, competencia.mes, monthrange(competencia.ano, competencia.mes)[1])
    incompletos = {f.id for f in funcionarios if not vinculo_permite_calendario(f)
        and vinculo_intersecta_periodo(f, inicio, fim)}
    faltantes = sum(1 for f in funcionarios if vinculo_permite_calendario(f) for n in range(1, fim.day + 1)
        if dentro_vinculo(f, date(competencia.ano, competencia.mes, n)) and (f.id, date(competencia.ano, competencia.mes, n).isoformat()) not in presentes)
    contagens = contagens_dias or {"problemas": sum(d["problema"] for d in dias),
        "aguardando_conferencia": sum(d["aguardando_conferencia"] for d in dias),
        "conferidos": sum(d["conferido"] for d in dias), "total": len(dias)}
    contagens.update(dias_sem_registro=faltantes,analises_pendentes=analises,
        conflitos_importacao=len(pendencias_importacao),total_arquivos=len(arquivos))
    if incompletos:
        contagens['vinculos_incompletos'] = len(incompletos)
        aviso = "Vínculo histórico incompleto: revise as datas de admissão e demissão no cadastro. Dias ausentes não foram presumidos."
        resultado['avisos_vinculo'] = [dict(funcionario_id=id, codigo='vinculo_historico_incompleto', mensagem=aviso)
                                      for id in sorted(incompletos)]
        for resumo in resultado.get('resumo', []):
            if resumo['funcionario_id'] in incompletos:
                resumo['observacoes'] = ' '.join(filter(None, (resumo.get('observacoes'), aviso)))
    motivos = []
    if not contagens["total"]: motivos.append("Não há registros processados.")
    if analises: motivos.append(f"{analises} arquivo(s) aguardam confirmação da importação.")
    if pendencias_importacao: motivos.append(f"{len(pendencias_importacao)} registro(s) de importação não resolvidos.")
    if contagens["problemas"]: motivos.append(f"{contagens['problemas']} dia(s) com problemas bloqueantes.")
    if contagens["aguardando_conferencia"]: motivos.append(f"{contagens['aguardando_conferencia']} dia(s) aguardam conferência.")
    if faltantes: motivos.append(f"{faltantes} dia(s) do vínculo sem registro. Inicialize o calendário ou confirme a importação.")
    fechada = competencia.status == "fechada"
    proxima = ("exportar" if fechada else "confirmar_importacao" if analises else
        "resolver_problemas" if contagens["problemas"] or pendencias_importacao else
        "importar" if not contagens["total"] else "continuar_conferencia" if contagens["aguardando_conferencia"] or faltantes else "revisar_fechar")
    resultado["operacional"] = contagens
    resultado["pendencias_importacao"] = pendencias_importacao
    resultado["fechamento"] = {"pode_fechar": not fechada and not motivos,
        "motivo_bloqueio": "A competência já está fechada." if fechada else " ".join(motivos) or None,
        "motivos": motivos, "proxima_acao": proxima}
    return resultado
