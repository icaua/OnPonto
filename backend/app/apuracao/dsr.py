from calendar import monthrange
import json
from datetime import date, timedelta

from sqlalchemy import or_
from app.database.models import MarcacaoPonto, Funcionario, OcorrenciaFuncionario
from app.calendario.service import dentro_vinculo, consultar_eventos, data_no_ano, abrange_empresa
from app.dominio.dsr import DiaReferenciaDSR, apurar_descanso
from app.dominio.apuracao import apurar_dia
from app.dominio.contratos import ContextoCalendario
from app.apuracao import adaptadores
from dataclasses import replace


def preparar_dsr(db, competencia, empresa, funcionarios, resolvedor):
    inicio = date(competencia.ano,competencia.mes,1)
    fim = date(competencia.ano,competencia.mes,monthrange(competencia.ano,competencia.mes)[1])
    # Nenhuma consulta adicional no legado sem DSR explicitamente configurado.
    tem_politica = any(resolvedor.regra_no_dia(f,inicio) and resolvedor.regra_no_dia(f,inicio).politica_dsr
                       or resolvedor.regra_no_dia(f,fim) and resolvedor.regra_no_dia(f,fim).politica_dsr for f in funcionarios)
    if not tem_politica:
        # Inclui versão com vigência curta interna ao mês.
        tem_politica = any(json.loads(v.configuracao_json).get("politica_dsr") for vs in resolvedor.versoes.values() for v in vs)
    if not tem_politica: return {}, {}
    janela_inicio,janela_fim = inicio-timedelta(days=6),fim+timedelta(days=6)
    feriados = {}
    for ano in range(janela_inicio.year,janela_fim.year+1):
        for evento in consultar_eventos(db,ano,tipo="FERIADO"):
            data = data_no_ano(evento,ano)
            if janela_inicio<=data<=janela_fim and evento.ativo and abrange_empresa(evento,empresa):
                feriados.setdefault(data,[]).append(evento.nome)
    marcacoes = {(m.funcionario_id,m.data):m for m in db.query(MarcacaoPonto).join(Funcionario)
                 .filter(Funcionario.empresa_id==empresa.id,MarcacaoPonto.data.between(janela_inicio,janela_fim))}
    ocorrencias = {}
    for o in db.query(OcorrenciaFuncionario).join(Funcionario).filter(Funcionario.empresa_id==empresa.id,
            OcorrenciaFuncionario.excluido_em.is_(None),OcorrenciaFuncionario.data_inicio<=janela_fim,
            or_(OcorrenciaFuncionario.data_fim.is_(None),OcorrenciaFuncionario.data_fim>=janela_inicio)):
        ocorrencias.setdefault(o.funcionario_id,[]).append(o)
    calculos, saida = {}, {}
    for f in funcionarios:
        semanas = {}
        for n in range((fim-inicio).days+1):
            dia = inicio+timedelta(days=n)
            regra = resolvedor.regra_no_dia(f,dia)
            if not regra or not regra.politica_dsr or not dentro_vinculo(f,dia): continue
            politica = regra.politica_dsr
            descanso = dia.weekday()==politica["dia_descanso"]
            feriado = bool(feriados.get(dia)) or bool(marcacoes.get((f.id,dia)) and marcacoes[f.id,dia].status_dia=="feriado")
            if not descanso and not feriado: continue
            referencia = dia+timedelta(days=(politica["dia_descanso"]-dia.weekday())%7)
            chave = (referencia,politica["dia_descanso"])
            if chave not in semanas:
                refs = []
                for anterior in (referencia-timedelta(days=i) for i in range(6,0,-1)):
                    m = marcacoes.get((f.id,anterior))
                    if not dentro_vinculo(f,anterior):
                        refs.append(DiaReferenciaDSR(anterior,False,None,None,None,False));continue
                    if m is None:
                        refs.append(DiaReferenciaDSR(anterior,True,None,None,None,False));continue
                    regra_anterior = resolvedor.regra_no_dia(f,anterior)
                    dto = replace(adaptadores.funcionario(f),escala=regra_anterior)
                    calculo = apurar_dia(dto,adaptadores.marcacoes(m),ContextoCalendario(tuple(feriados.get(anterior,[]))),
                        adaptadores.ocorrencias(ocorrencias.get(f.id,[])))
                    calculos[m.id] = calculo
                    d = calculo.dados_legados
                    transicao = bool(regra_anterior and regra_anterior.politica_dsr and regra_anterior.politica_dsr["dia_descanso"]!=politica["dia_descanso"])
                    refs.append(DiaReferenciaDSR(anterior,True,m.id,m.revisao,d["status_dia"],d["conferido"],d["problema"] or transicao))
                semanas[chave] = apurar_descanso(referencia,refs)
            dsr = dict(semanas[chave],tipo="descanso_e_feriado" if descanso and feriado else "descanso" if descanso else "feriado",dias=1,
                       politica=politica,escala_versao_id=regra.versao_id)
            if feriado and not descanso and not politica["descontar_feriados"]: dsr["desconto_dias"]=0
            saida[f.id,dia] = dsr
    return saida,calculos


def resumir_dsr(resumos, dias):
    for resumo in resumos:
        registros = [d["dsr"] for d in dias if d["funcionario_id"]==resumo["funcionario_id"] and d.get("dsr")]
        if registros:
            resumo["dsr_dias"] = len(registros)
            resumo["dsr_desconto_dias"] = None if any(d["desconto_dias"] is None for d in registros) else sum(d["desconto_dias"] for d in registros)
