"""Dados exclusivamente fictícios e determinísticos para regressão e medição."""
import json
from calendar import monthrange
from datetime import date, time

from app.database.models import (Empresa, Escala, Funcionario, Competencia,
    MarcacaoPonto, HistoricoVinculoEscala, EventoCalendario, OcorrenciaFuncionario)


def criar_cenario(db, quantidade=10):
    empresa = Empresa(nome="Empresa FICTÍCIA baseline", prazo_compensacao_banco_horas_dias=180)
    db.add(empresa)
    db.flush()
    escalas = [
        Escala(empresa_id=empresa.id, nome="Fixo legado", modo_apuracao="horario_fixo",
            horario_entrada_prevista=time(8), horario_saida_almoco_prevista=time(12),
            horario_retorno_almoco_prevista=time(13), horario_saida_prevista=time(17),
            tolerancia_atraso_minutos=5, tolerancia_extra_minutos=10),
        Escala(empresa_id=empresa.id, nome="Carga e sábado 4h", jornada_seg_sex_horas=8,
            regime_sabado="trabalha", jornada_sabado_horas=4, usa_banco_horas=True),
        Escala(empresa_id=empresa.id, nome="Política mista fictícia", jornada_seg_sex_horas=8,
            politica_horas={"modo":"misto", "percentual_folha":50, "percentual_banco":50,
                "adicional_folha_percentual":60, "inicio_ciclo":"2026-09-01", "ciclo_dias":180},
            usa_banco_horas=True),
    ]
    db.add_all(escalas)
    db.flush()
    competencias = [Competencia(empresa_id=empresa.id, ano=2026, mes=mes) for mes in (9, 10)]
    db.add_all(competencias)
    db.flush()
    for c in competencias:
        db.add(EventoCalendario(nome="Feriado FICTÍCIO", data=date(2026,c.mes,7), tipo="feriado",
            abrangencia="empresa", empresa_id=empresa.id))
    for i in range(quantidade):
        escala = escalas[i % len(escalas)]
        funcionario = Funcionario(empresa_id=empresa.id, escala_id=escala.id,
            nome=f"Pessoa FICTÍCIA {i:04d}", codigo=f"F{i:04d}", data_admissao=date(2026,9,1))
        db.add(funcionario)
        db.flush()
        db.add(HistoricoVinculoEscala(funcionario_id=funcionario.id, escala_id=escala.id,
            vigente_desde=date(2026,9,1)))
        for c in competencias:
            for dia in range(1,monthrange(c.ano,c.mes)[1]+1):
                data = date(c.ano,c.mes,dia)
                entrada, almoco, retorno, saida = time(8),time(12),time(13),time(17)
                status = "normal"
                if data.weekday() == 6 or (data.weekday() == 5 and escala.regime_sabado != "trabalha"):
                    entrada=almoco=retorno=saida=None
                    status="domingo" if data.weekday()==6 else "sem_expediente"
                elif data.weekday() == 5:
                    entrada,almoco,retorno,saida=time(8),None,None,time(12)
                if dia == 7:
                    entrada=almoco=retorno=saida=None
                    status="feriado"
                if c.mes==10 and dia==2: saida=time(18)
                if c.mes==10 and dia==5: entrada=time(8,20)
                if dia == 1:
                    # Matriz de bordas no mês de setembro; outubro é fechável.
                    caso=i % 10 if c.mes == 9 else 0
                    if caso == 1: entrada=time(8,16)
                    if caso == 2: saida=time(18)
                    if caso == 3: almoco=retorno=None  # duas batidas legadas
                    if caso == 4: retorno=None  # intervalo incompleto
                    if caso in (5,6):
                        entrada=almoco=retorno=saida=None
                        status="falta" if caso==5 else "atestado"
                    if caso == 6:
                        db.add(OcorrenciaFuncionario(funcionario_id=funcionario.id, tipo="ATESTADO",
                            data_inicio=data, data_fim=data))
                    if caso == 7:
                        entrada=time(9)
                        db.add(OcorrenciaFuncionario(funcionario_id=funcionario.id, tipo="DECLARACAO",
                            data_inicio=data, data_fim=data, hora_inicio=time(8), hora_fim=time(9)))
                batidas=[h.isoformat() for h in (entrada,almoco,retorno,saida) if h]
                if c.mes == 9 and dia == 1 and i % 10 in (8,9):
                    batidas.insert(1,"08:01:00")
                marcacao=MarcacaoPonto(competencia_id=c.id,funcionario_id=funcionario.id,data=data,
                    entrada=entrada,saida_almoco=almoco,retorno_almoco=retorno,saida=saida,
                    status_dia=status,conferido=not(c.mes==9 and dia==1),origem="manual",
                    batidas_originais=json.dumps(batidas))
                if c.mes==9 and dia==1 and i % 10==9:
                    marcacao.batidas_desconsideradas_json=json.dumps([
                        {"indice":1,"horario":"08:01:00","justificativa":"Duplicidade FICTÍCIA"}])
                db.add(marcacao)
    db.commit()
    return {"empresa":empresa.id,"aberta":competencias[0].id,"fechavel":competencias[1].id}


def normalizar(valor):
    """Apenas metadados voláteis; nunca remover resultados de cálculo."""
    if isinstance(valor,dict):
        return {k:normalizar(v) for k,v in valor.items() if k not in
            {"gerado_em","created_at","updated_at","em","estornado_em","estornada_em","data_lancamento"}}
    if isinstance(valor,list): return [normalizar(v) for v in valor]
    return valor
