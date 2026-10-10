from app.dominio import apuracao as motor
from app.apuracao import adaptadores
from app.apuracao.dsr import preparar_dsr, resumir_dsr
from app.dominio.contratos import ContextoCalendario
# Nomes públicos preservados para módulos e ferramentas existentes.
from app.dominio.apuracao import (minutos_hora,diferenca_minutos,formatar_minutos,formatar_hora,
    jornada_horario_fixo_minutos,jornada_prevista_minutos,tolerancia_intervalo_efetiva,
    horario_fixo_configurado,calcular_atraso_horario_fixo,calcular_trabalhado,STATUS_SEM_CALCULO)
from types import SimpleNamespace
from app.banco_horas.regras import distribuir_dia, resumir_distribuicao
from app.funcionarios.historico_escalas import ResolvedorEscalas
from app.marcacoes.batidas import desconsideradas_em_uso
from app.apuracao.operacional import classificar_dia, indicadores, contar_batidas_originais
from calendar import monthrange
import json
from datetime import date, datetime, time
from typing import Any

from sqlalchemy.orm import Session
from app.ocorrencias.service import consultar as consultar_ocorrencias
from app.banco_horas.service import complementar_apuracao, bloqueios_saldo_projetado
from app.calendario.service import dentro_vinculo, feriados_da_competencia, motivo_fora_vinculo, vinculo_intersecta_periodo

from app.database.models import (
    ArquivoRecebido,
    Competencia,
    Escala,
    Funcionario,
    MarcacaoPonto,
)


STATUS_AUTOMATICOS_CALENDARIO = {
    ("normal", False),
    ("domingo", True),
    ("sem_expediente", True),
}


def configuracao_calendario(funcionario: Funcionario, data_referencia: date) -> tuple[str, bool]:
    escala = funcionario.escala
    if not escala:
        return "normal", False
    if getattr(escala,"politica_dsr",None) and data_referencia.weekday()==escala.politica_dsr["dia_descanso"]:
        return "sem_expediente",True

    dia_semana = data_referencia.weekday()
    if dia_semana == 6:
        if escala.regime_domingo == "nao_trabalha":
            return "domingo", True
        if getattr(escala,"jornada_dia_minutos",None)==0: return "sem_expediente",True
        return "normal", False
    if dia_semana == 5:
        if escala.regime_sabado in {"compensado", "nao_trabalha"}:
            return "sem_expediente", True
        if getattr(escala,"jornada_dia_minutos",None)==0: return "sem_expediente",True
        return "normal", False
    if getattr(escala,"jornada_dia_minutos",None)==0:
        return "sem_expediente",True
    return "normal", False


def placeholder_calendario_intocado(marcacao: MarcacaoPonto) -> bool:
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


def gerar_dias_faltantes(db: Session, competencia: Competencia) -> int:
    """Gera o calendário no primeiro processamento da competência, sem commit.

    O helper só faz ``flush`` para participar da transação do chamador. Isso mantém
    idempotentes chamadas repetidas na mesma sessão e deixa a fronteira de commit
    na apuração, nos relatórios e nas ações de fechamento/reabertura que o chamam.
    """

    if competencia.status == "fechada":
        return 0
    db.flush()
    funcionarios = (
        db.query(Funcionario)
        .filter(
            Funcionario.empresa_id == competencia.empresa_id,
            Funcionario.ativo.is_(True),
        )
        .all()
    )
    if not funcionarios:
        return 0

    existentes = {
        (marcacao.funcionario_id, marcacao.data): marcacao
        for marcacao in (
            db.query(MarcacaoPonto)
            .filter(MarcacaoPonto.competencia_id == competencia.id)
            .all()
        )
    }
    ultimo_dia = monthrange(competencia.ano, competencia.mes)[1]
    resolvedor=ResolvedorEscalas(db,competencia.empresa_id)
    from app.database.models import DependenciaFechamento
    referenciadas={id for id, in db.query(DependenciaFechamento.marcacao_id).join(MarcacaoPonto,
                  MarcacaoPonto.id==DependenciaFechamento.marcacao_id).filter(MarcacaoPonto.competencia_id==competencia.id)}
    criadas = 0
    for funcionario in funcionarios:
        for dia in range(1, ultimo_dia + 1):
            data_marcacao = date(competencia.ano, competencia.mes, dia)
            chave = (funcionario.id, data_marcacao)
            contexto=SimpleNamespace(escala=resolvedor.regra_no_dia(funcionario,data_marcacao))
            existente = existentes.get(chave)
            if existente is not None and existente.id in referenciadas:
                continue
            if not dentro_vinculo(funcionario, data_marcacao):
                if existente is not None and placeholder_calendario_intocado(existente):
                    db.delete(existente)
                continue
            if existente is not None:
                # Um placeholder automático acompanha mudanças posteriores da
                # escala. Marcações importadas ou já tocadas pelo usuário nunca
                # são reinterpretadas aqui.
                if placeholder_calendario_intocado(existente):
                    status_dia, conferido = configuracao_calendario(
                        contexto,
                        data_marcacao,
                    )
                    existente.status_dia = status_dia
                    existente.conferido = conferido
                continue
            status_dia, conferido = configuracao_calendario(contexto, data_marcacao)
            nova_marcacao = MarcacaoPonto(
                competencia_id=competencia.id,
                funcionario_id=funcionario.id,
                data=data_marcacao,
                status_dia=status_dia,
                origem="calendario",
                conferido=conferido,
            )
            db.add(nova_marcacao)
            existentes[chave] = nova_marcacao
            criadas += 1

    db.flush()
    return criadas


def detalhe_marcacao(funcionario,marcacao,feriados=None):
    return motor.detalhe_marcacao(adaptadores.funcionario(funcionario),adaptadores.marcacoes(marcacao),feriados)


def detalhe_fora_vinculo(funcionario,marcacao):
    return motor.detalhe_fora_vinculo(adaptadores.funcionario(funcionario),adaptadores.marcacoes(marcacao))


def apurar_competencia(
    db: Session,
    competencia_id: int,
    *,
    gerar_calendario: bool = False,
    incluir_banco: bool = True,
) -> dict[str, Any] | None:
    competencia = db.get(Competencia, competencia_id)
    if not competencia:
        return None

    if competencia.status == "fechada":
        if competencia.apuracao_fechada:
            resultado = json.loads(competencia.apuracao_fechada)
            if resultado.get("snapshot_versao", 0) >= 2:
                return resultado
            return complementar_apuracao(db, competencia, resultado) if incluir_banco else resultado
        gerar_calendario = False

    if gerar_calendario:
        gerar_dias_faltantes(db, competencia)

    from app.apuracao.contexto import ContextoApuracao
    contexto_apuracao=ContextoApuracao(db,competencia)
    empresa=contexto_apuracao.empresa
    funcionarios=contexto_apuracao.funcionarios
    funcionarios_por_id=contexto_apuracao.por_id
    resolvedor_escalas=contexto_apuracao.resolvedor

    resumo = {
        funcionario.id: {
            "funcionario_id": funcionario.id,
            "funcionario": (getattr(funcionario, "nome_exibicao", None) or funcionario.nome),
            "codigo": funcionario.codigo_apresentacao,
            "nome_original": funcionario.nome,
            "codigo_original": funcionario.codigo,
            "dias_processados": 0,
            "atrasos_minutos": 0,
            "extras_minutos": 0,
            "atrasos": "00:00",
            "extras": "00:00",
            "horas_feriado_minutos": 0,
            "horas_feriado": "00:00",
            "_horas_feriado_pendentes": False,
            "faltas": 0,
            "atestados": 0,
            "pendencias": 0,
            "problemas": 0,
            "aguardando_conferencia": 0,
            "conferidos": 0,
            "situacao": "indisponivel",
            "observacoes": "",
            "_duracoes_disponiveis": True,
        }
        for funcionario in funcionarios
    }

    detalhes=contexto_apuracao.detalhes()
    pendencias=[]
    dias_com_pendencia=set()
    for detalhe in detalhes:
        funcionario=funcionarios_por_id[detalhe['funcionario_id']]
        item_resumo = resumo[funcionario.id]
        item_resumo["dias_processados"] += int(not detalhe["fora_vinculo"])
        item_resumo["atrasos_minutos"] += detalhe["atraso_minutos"]
        item_resumo["extras_minutos"] += detalhe["extra_minutos"]
        item_resumo["horas_feriado_minutos"] += detalhe["horas_feriado_minutos"]
        item_resumo["_horas_feriado_pendentes"] |= detalhe["horas_feriado_pendente"]
        item_resumo["faltas"] += detalhe["falta"]
        item_resumo["atestados"] += detalhe["atestado"]
        item_resumo["problemas"] += int(detalhe["problema"])
        item_resumo["aguardando_conferencia"] += int(detalhe["aguardando_conferencia"])
        item_resumo["conferidos"] += int(detalhe["conferido"])
        if detalhe["pendente_calculo"]:
            item_resumo["_duracoes_disponiveis"] = False
        if detalhe["pendente"]:
            item_resumo["pendencias"] += 1
            pendencias.append(detalhe)
            dias_com_pendencia.add((funcionario.id, detalhe["data"]))

    for item in resumo.values():
        if item.pop("_horas_feriado_pendentes"):
            item["horas_feriado_minutos"] = None
        item["horas_feriado"] = formatar_minutos(item["horas_feriado_minutos"])
        motivos_vinculo = {d["pendencia_tipo"] for d in pendencias if d["funcionario_id"] == item["funcionario_id"] and d.get("fora_vinculo")}
        if motivos_vinculo:
            item["observacoes"] = "; ".join(texto for tipo, texto in [
                ("marcacao_anterior_admissao", "Existem marcações anteriores à admissão"),
                ("marcacao_posterior_demissao", "Existem marcações posteriores à demissão"),
            ] if tipo in motivos_vinculo)
        fora_competencia = not vinculo_intersecta_periodo(funcionarios_por_id[item["funcionario_id"]],
            date(competencia.ano, competencia.mes, 1),
            date(competencia.ano, competencia.mes, monthrange(competencia.ano, competencia.mes)[1]))
        if item["dias_processados"] == 0 and (fora_competencia or item["pendencias"]):
            item["situacao"] = "pendente" if item["pendencias"] else "fora_vinculo"
            if not item["observacoes"]:
                item["observacoes"] = "Fora do vínculo nesta competência"
        elif item["dias_processados"] == 0:
            item["atrasos_minutos"] = None
            item["extras_minutos"] = None
            item["atrasos"] = None
            item["extras"] = None
            item["faltas"] = None
            item["atestados"] = None
            item["pendencias"] = None
            item["situacao"] = "indisponivel"
        else:
            if item["_duracoes_disponiveis"]:
                item["atrasos"] = formatar_minutos(item["atrasos_minutos"])
                item["extras"] = formatar_minutos(item["extras_minutos"])
            else:
                item["atrasos_minutos"] = None
                item["extras_minutos"] = None
                item["atrasos"] = None
                item["extras"] = None
            item["situacao"] = "pendente" if item["pendencias"] else "conferido"
        del item["_duracoes_disponiveis"]

    resumo_funcionarios = list(resumo.values())
    resumir_distribuicao(resumo_funcionarios, detalhes)
    resumir_dsr(resumo_funcionarios, detalhes)
    resumo_geral = {
        "funcionarios": len(resumo_funcionarios),
        "conferidos": sum(1 for item in resumo_funcionarios if item["situacao"] == "conferido"),
        "pendentes": sum(1 for item in resumo_funcionarios if item["situacao"] == "pendente"),
        "dias_com_pendencia": len(dias_com_pendencia),
        "total_arquivos": (
            db.query(ArquivoRecebido)
            .filter(ArquivoRecebido.competencia_id == competencia.id)
            .count()
        ),
    }

    resultado = {
        "empresa": {
            "id": empresa.id,
            "nome": empresa.nome,
            "cnpj": empresa.cnpj,
        },
        "competencia": {
            "id": competencia.id,
            "mes": competencia.mes,
            "ano": competencia.ano,
            "label": f"{competencia.mes:02d}/{competencia.ano}",
            "status": competencia.status,
        },
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "resumo_geral": resumo_geral,
        "resumo": resumo_funcionarios,
        "marcacoes": detalhes,
        "pendencias": pendencias,
    }
    indicadores(resultado, funcionarios, contexto_apuracao.arquivos, competencia,
        arquivos_com_marcacoes=contexto_apuracao.arquivos_com_marcacoes)
    from app.banco_horas.consulta import LedgerEmMemoria
    ledger=LedgerEmMemoria(db,funcionarios_por_id)
    bloqueios = bloqueios_saldo_projetado(db, resultado,ledger=ledger)
    resultado["bloqueios_politica"] = bloqueios
    if bloqueios:
        decisao = resultado["fechamento"]
        decisao["motivos"].extend(bloqueios)
        decisao.update(pode_fechar=False, motivo_bloqueio=" ".join(decisao["motivos"]))
        if not resultado["operacional"]["problemas"] and not resultado["pendencias_importacao"]:
            decisao["proxima_acao"] = "revisar_banco"
    return complementar_apuracao(db, competencia, resultado, resolvedor_escalas=resolvedor_escalas,
        ledger=ledger,funcionarios_por_id=funcionarios_por_id) if incluir_banco else resultado
