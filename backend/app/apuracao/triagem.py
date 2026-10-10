"""Projeção descartável da conferência; fechamento nunca consome este cache."""
import json
from datetime import datetime
from app.apuracao.contexto import ContextoApuracao
from app.apuracao.operacional import indicadores
from app.database.models import Competencia, CacheConferencia


def consultar_triagem(db, competencia_id, *, persistir=False):
    c=db.get(Competencia,competencia_id)
    if c is None: return None
    if c.status=="fechada" and c.apuracao_fechada:
        salvo=json.loads(c.apuracao_fechada)
        return {k:v for k,v in salvo.items() if k not in ("marcacoes","pendencias")}
    contexto=ContextoApuracao(db,c)
    cache={r.funcionario_id:r for r in db.query(CacheConferencia).filter_by(competencia_id=c.id)}
    linhas,presentes=[],set()
    totais={k:0 for k in ("problemas","aguardando_conferencia","conferidos","total")}
    for f in contexto.funcionarios:
        assinatura=contexto.assinatura(f)
        registro=cache.get(f.id)
        if registro and registro.assinatura==assinatura:
            contagens=json.loads(registro.contadores_json)
        else:
            dias=contexto.detalhes(f.id)
            contagens={k:sum(bool(d[k]) for d in dias) for k in ("problema","aguardando_conferencia","conferido")}
            contagens.update(total=len(dias),datas=[d["data"] for d in dias],dias_processados=sum(not d["fora_vinculo"] for d in dias))
            if persistir:
                if registro is None:
                    registro=CacheConferencia(competencia_id=c.id,funcionario_id=f.id)
                    db.add(registro)
                registro.assinatura=assinatura
                registro.contadores_json=json.dumps(contagens,ensure_ascii=False)
        presentes.update((f.id,d) for d in contagens["datas"])
        totais["problemas"]+=contagens["problema"]
        totais["conferidos"]+=contagens["conferido"]
        totais["aguardando_conferencia"]+=contagens["aguardando_conferencia"]
        totais["total"]+=contagens["total"]
        pendencias=contagens["problema"]+contagens["aguardando_conferencia"]
        linhas.append(dict(funcionario_id=f.id,funcionario=f.nome_apresentacao,codigo=f.codigo_apresentacao,
            nome_original=f.nome,codigo_original=f.codigo,problemas=contagens["problema"],
            aguardando_conferencia=contagens["aguardando_conferencia"],conferidos=contagens["conferido"],
            dias_processados=contagens["dias_processados"],pendencias=pendencias,
            situacao="pendente" if pendencias else "conferido" if contagens["total"] else "indisponivel"))
    resultado=dict(empresa={"id":contexto.empresa.id,"nome":contexto.empresa.nome,"cnpj":contexto.empresa.cnpj},
        competencia={"id":c.id,"ano":c.ano,"mes":c.mes,"label":f"{c.mes:02d}/{c.ano}","status":c.status},
        resumo=linhas,marcacoes=[],gerado_em=datetime.now().isoformat(timespec="seconds"),
        origem="triagem_derivada",apuracao_integral=False)
    indicadores(resultado,contexto.funcionarios,contexto.arquivos,c,
        arquivos_com_marcacoes=contexto.arquivos_com_marcacoes,contagens_dias=totais,presentes=presentes)
    # Triagem operacional nunca promete aprovação das regras financeiras do ledger.
    resultado["fechamento"]["validacao_integral_necessaria"]=True
    resultado["resumo_geral"]={"funcionarios":len(linhas),"conferidos":sum(r["situacao"]=="conferido" for r in linhas),
        "pendentes":sum(r["situacao"]=="pendente" for r in linhas),"dias_com_pendencia":totais["problemas"]+totais["aguardando_conferencia"],
        "total_arquivos":len(contexto.arquivos)}
    resultado.pop("marcacoes")
    return resultado
