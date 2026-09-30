"""Validação da folga: consome os cálculos existentes e não inventa atraso."""
from datetime import timedelta
from types import SimpleNamespace

from fastapi import HTTPException

from app.banco_horas.service import calcular_saldo_banco_horas, obter_funcionario
from app.banco_horas.regras import politica_da_escala, ciclo
from app.banco_horas.service import situacao_lancamentos
from app.database.models import Competencia, MarcacaoPonto, OcorrenciaFuncionario
from app.funcionarios.historico_escalas import registrar_vinculo_inicial, escala_no_dia


def minutos_reservados(db, funcionario, ocorrencia, por_ciclo=False):
    from app.apuracao.service import detalhe_marcacao
    from app.calendario.service import dentro_vinculo, feriados_da_competencia
    from app.ocorrencias.interpretacao import aplicar_ocorrencias
    total, dia = 0, ocorrencia.data_inicio
    grupos = {}
    feriados = {}
    while dia <= ocorrencia.data_fim:
        competencia = db.query(Competencia).filter_by(empresa_id=funcionario.empresa_id, mes=dia.month, ano=dia.year).first()
        if competencia and competencia.status == "fechada":
            dia += timedelta(days=1)
            continue  # O consumo desta competência já está no ledger.
        if not dentro_vinculo(funcionario, dia):
            raise HTTPException(409, "Folga compensatória fora do período de vínculo do funcionário.")
        escala = escala_no_dia(db, funcionario, dia)
        if not escala or not escala.usa_banco_horas:
            raise HTTPException(409, "Folga compensatória exige escala com banco de horas no período informado.")
        if (dia.year, dia.month) not in feriados:
            feriados[(dia.year, dia.month)] = feriados_da_competencia(db, funcionario.empresa, dia.year, dia.month)
        marcacao = db.query(MarcacaoPonto).filter_by(funcionario_id=funcionario.id, data=dia).first()
        if not marcacao:
            marcacao = MarcacaoPonto(funcionario_id=funcionario.id, data=dia, status_dia="normal", conferido=False)
        contexto = SimpleNamespace(**{c.name: getattr(funcionario, c.name) for c in funcionario.__table__.columns},
                                   escala=escala, empresa=funcionario.empresa)
        detalhe = detalhe_marcacao(contexto, marcacao, feriados[(dia.year, dia.month)])
        aplicar_ocorrencias(detalhe, contexto, marcacao, [ocorrencia])
        if detalhe["pendente_calculo"]:
            raise HTTPException(409, "Folga compensatória: " + detalhe["pendencia_motivo"])
        total += detalhe.get("minutos_folga_compensatoria", 0)
        politica = politica_da_escala(escala)
        inicio, fim = ciclo(politica, dia) if politica else (None, None)
        chave = (inicio, fim, bool(politica and politica.permite_saldo_negativo))
        grupos[chave] = grupos.get(chave, 0) + detalhe.get("minutos_folga_compensatoria", 0)
        dia += timedelta(days=1)
    return grupos if por_ciclo else total


def validar_folga(db, dados, ignorar_id=None):
    if dados.tipo != "FOLGA_COMPENSATORIA":
        return
    funcionario = obter_funcionario(db, dados.funcionario_id)
    registrar_vinculo_inicial(db, funcionario)
    nova = SimpleNamespace(id=ignorar_id or 0, **dados.model_dump())
    necessarios = minutos_reservados(db, funcionario, nova, por_ciclo=True)
    reservados = {}
    for outra in db.query(OcorrenciaFuncionario).filter_by(funcionario_id=funcionario.id,
            tipo="FOLGA_COMPENSATORIA", excluido_em=None):
        if outra.id != ignorar_id:
            for (inicio, fim, _), minutos in minutos_reservados(db, funcionario, outra, por_ciclo=True).items():
                reservados[(inicio, fim)] = reservados.get((inicio, fim), 0) + minutos
    situacao = situacao_lancamentos(db, funcionario.id)
    for (inicio, fim, negativo), minutos in necessarios.items():
        if negativo:
            continue
        saldo = sum(restante if i.natureza == "credito" else -restante for i, _, restante in situacao
                    if (i.ciclo_inicio, i.ciclo_fim) == (inicio, fim))
        disponiveis = max(saldo - reservados.get((inicio, fim), 0), 0)
        if minutos > disponiveis:
            raise HTTPException(409, f"Saldo insuficiente para folga compensatória: necessários {minutos} min, disponíveis {disponiveis} min após outras folgas reservadas. Revise a ocorrência ou registre um ajuste justificado no banco.")
