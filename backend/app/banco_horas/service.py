"""Serviços transacionais do ledger. O chamador é responsável pelo commit."""
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException

from app.banco_horas.politica import hoje_local, validar_prazo, vencimento_credito
from app.database.models import Funcionario, LancamentoBancoHoras, CompensacaoBancoHoras
from app.funcionarios.historico_escalas import registrar_vinculo_inicial, escala_no_dia


def gerar_lancamentos(db, competencia, resultado):
    """Consome a única apuração obtida pelo fechamento, sem recalcular o ponto."""
    funcionarios = {f.id: f for f in db.query(Funcionario).filter_by(empresa_id=competencia.empresa_id)}
    for funcionario in funcionarios.values():
        registrar_vinculo_inicial(db, funcionario)
    gerados = []
    for dia in sorted(resultado["marcacoes"], key=lambda d: (d["data"], d["funcionario_id"])):
        funcionario = funcionarios[dia["funcionario_id"]]
        referencia = date.fromisoformat(dia["data"])
        escala = escala_no_dia(db, funcionario, referencia)
        if dia.get("minutos_folga_compensatoria", 0) and (not escala or not escala.usa_banco_horas):
            raise HTTPException(409, "A folga compensatória exige banco de horas habilitado na escala de origem. Revise a ocorrência antes de fechar.")
        if not escala or not escala.usa_banco_horas or dia.get("fora_vinculo"):
            continue
        if dia.get("pendente_calculo"):
            raise HTTPException(409, f"Banco de horas: resolva a pendência de cálculo de {funcionario.nome} em {referencia:%d/%m/%Y} antes de fechar.")
        prazo = validar_prazo(competencia.empresa)
        credito = dia.get("extra_minutos") or 0
        if competencia.empresa.feriado_entra_banco:
            credito += dia.get("horas_feriado_minutos") or 0
        debito = dia.get("atraso_minutos") or 0
        dia["banco_horas_regra"] = {"escala_origem_id": escala.id, "prazo_compensacao_aplicado_dias": prazo,
                                   "feriado_entra_banco": competencia.empresa.feriado_entra_banco}
        for natureza, minutos, origem in (("credito", credito, "apuracao"), ("debito", debito, "apuracao"),
                ("debito", dia.get("minutos_folga_compensatoria", 0), "folga_compensatoria")):
            if minutos <= 0:
                continue
            item = LancamentoBancoHoras(funcionario_id=funcionario.id, empresa_id=competencia.empresa_id,
                competencia_origem_id=competencia.id, escala_origem_id=escala.id,
                natureza=natureza, origem=origem, minutos=minutos, data_referencia=referencia,
                data_lancamento=competencia.data_fechamento,
                data_vencimento=vencimento_credito(referencia, prazo) if natureza == "credito" else None,
                prazo_compensacao_aplicado_dias=prazo, feriado_entra_banco_aplicado=competencia.empresa.feriado_entra_banco,
                versao_fechamento=competencia.versao_fechamento)
            db.add(item)
            gerados.append(item)
    db.flush()
    return gerados


def validar_cobertura_folgas(db, gerados):
    ids = {i.id for i in gerados if i.origem == "folga_compensatoria"}
    for funcionario_id in {i.funcionario_id for i in gerados if i.id in ids}:
        for item, _, restante in situacao_lancamentos(db, funcionario_id):
            if item.id in ids and restante:
                raise HTTPException(409, f"Saldo insuficiente para folga compensatória em {item.data_referencia:%d/%m/%Y}: faltam {restante} min. O fechamento foi cancelado; revise a ocorrência ou o saldo do banco.")


def reconciliar(db, funcionario_id, motivo="Reconciliação dos lançamentos ativos"):
    """Reproduz a ordem de entrada; mantém compensações idênticas e audita mudanças."""
    db.flush()
    itens = (db.query(LancamentoBancoHoras).filter_by(funcionario_id=funcionario_id, status="ativo")
             .order_by(LancamentoBancoHoras.data_lancamento, LancamentoBancoHoras.id).all())
    restantes = {i.id: i.minutos for i in itens}
    creditos, debitos, esperadas = [], [], {}
    for item in itens:
        if item.natureza == "credito":
            candidatos = sorted(debitos, key=lambda i: (i.data_referencia, i.id))
            creditos.append(item)
        else:
            candidatos = sorted(creditos, key=lambda i: (i.data_vencimento or date.max, i.data_referencia, i.id))
            debitos.append(item)
        for outro in candidatos:
            minutos = min(restantes[item.id], restantes[outro.id])
            if minutos:
                credito, debito = (item, outro) if item.natureza == "credito" else (outro, item)
                esperadas[(credito.id, debito.id)] = minutos
                restantes[item.id] -= minutos
                restantes[outro.id] -= minutos
            if restantes[item.id] == 0:
                break
    todas_ids = [i[0] for i in db.query(LancamentoBancoHoras.id).filter_by(funcionario_id=funcionario_id)]
    atuais = db.query(CompensacaoBancoHoras).filter(CompensacaoBancoHoras.credito_id.in_(todas_ids),
                                                  CompensacaoBancoHoras.status == "ativo").all()
    for compensacao in atuais:
        chave = (compensacao.credito_id, compensacao.debito_id)
        if esperadas.get(chave) == compensacao.minutos:
            del esperadas[chave]
        else:
            compensacao.status = "estornado"
            compensacao.estornada_em = datetime.now(timezone.utc)
            compensacao.motivo_estorno = motivo
    db.flush()
    for (credito_id, debito_id), minutos in esperadas.items():
        db.add(CompensacaoBancoHoras(credito_id=credito_id, debito_id=debito_id, minutos=minutos))
    db.flush()


def situacao_lancamentos(db, funcionario_id, data_limite=None, incluir_estornados=False):
    query = db.query(LancamentoBancoHoras).filter_by(funcionario_id=funcionario_id)
    if data_limite:
        query = query.filter(LancamentoBancoHoras.data_referencia <= data_limite)
    if not incluir_estornados:
        query = query.filter_by(status="ativo")
    itens = query.order_by(LancamentoBancoHoras.data_referencia, LancamentoBancoHoras.data_lancamento, LancamentoBancoHoras.id).all()
    ativos = {i.id for i in itens if i.status == "ativo"}
    consumidos = {i.id: 0 for i in itens}
    # Um débito futuro não consome o saldo de uma consulta com corte anterior.
    for c in db.query(CompensacaoBancoHoras).filter(CompensacaoBancoHoras.status == "ativo",
            CompensacaoBancoHoras.credito_id.in_(ativos), CompensacaoBancoHoras.debito_id.in_(ativos)):
        consumidos[c.credito_id] += c.minutos
        consumidos[c.debito_id] += c.minutos
    return [(i, consumidos[i.id], i.minutos - consumidos[i.id] if i.status == "ativo" else 0) for i in itens]


def calcular_saldo_banco_horas(db, funcionario_id, data_limite=None):
    return sum(restante if i.natureza == "credito" else -restante
               for i, _, restante in situacao_lancamentos(db, funcionario_id, data_limite))


def obter_funcionario(db, funcionario_id):
    funcionario = db.get(Funcionario, funcionario_id)
    if not funcionario:
        raise HTTPException(404, "Funcionário não encontrado.")
    return funcionario


def ajustar(db, payload):
    funcionario = obter_funcionario(db, payload.funcionario_id)
    if payload.data_referencia > hoje_local():
        raise HTTPException(422, "Ajustes manuais não podem ter data de referência futura.")
    prazo = validar_prazo(funcionario.empresa) if payload.natureza == "credito" else None
    item = LancamentoBancoHoras(**payload.model_dump(), empresa_id=funcionario.empresa_id,
        origem="ajuste_manual", escala_origem_id=funcionario.escala_id,
        data_lancamento=hoje_local(), prazo_compensacao_aplicado_dias=prazo,
        data_vencimento=vencimento_credito(payload.data_referencia, prazo) if prazo else None,
        feriado_entra_banco_aplicado=funcionario.empresa.feriado_entra_banco)
    db.add(item); db.flush()
    reconciliar(db, funcionario.id, "Novo ajuste manual")
    return item


def estornar_ajuste(db, lancamento_id, motivo):
    item = db.get(LancamentoBancoHoras, lancamento_id)
    if not item:
        raise HTTPException(404, "Lançamento não encontrado.")
    if item.origem != "ajuste_manual":
        raise HTTPException(409, "Lançamento automático: reabra a competência de origem para corrigir.")
    if item.status != "ativo":
        raise HTTPException(409, "O lançamento já está estornado.")
    item.status = "estornado"
    item.estornado_em = datetime.now(timezone.utc)
    item.motivo_estorno = motivo
    reconciliar(db, item.funcionario_id, motivo)
    return item


def estornar_competencia(db, competencia):
    motivo = f"Competência {competencia.mes:02d}/{competencia.ano} reaberta (versão {competencia.versao_fechamento})"
    itens = db.query(LancamentoBancoHoras).filter_by(competencia_origem_id=competencia.id,
        versao_fechamento=competencia.versao_fechamento, status="ativo").all()
    funcionarios = {i.funcionario_id for i in itens}
    for item in itens:
        item.status = "estornado"
        item.estornado_em = datetime.now(timezone.utc)
        item.motivo_estorno = motivo
    db.flush()
    for funcionario_id in sorted(funcionarios):
        reconciliar(db, funcionario_id, motivo)


def extrato(db, funcionario_id, data_limite=None):
    funcionario = obter_funcionario(db, funcionario_id)
    linhas, acumulado = [], 0
    for item, consumidos, restantes in situacao_lancamentos(db, funcionario_id, data_limite, True):
        if item.status == "ativo":
            acumulado += item.minutos if item.natureza == "credito" else -item.minutos
        linha = {c.name: getattr(item, c.name) for c in LancamentoBancoHoras.__table__.columns}
        linha.update(minutos_compensados=consumidos, minutos_restantes=restantes, saldo_acumulado_minutos=acumulado)
        linhas.append(linha)
    ids = [i["id"] for i in linhas]
    compensacoes = db.query(CompensacaoBancoHoras).filter(
        (CompensacaoBancoHoras.credito_id.in_(ids)) | (CompensacaoBancoHoras.debito_id.in_(ids))).order_by(CompensacaoBancoHoras.id).all()
    return {"funcionario_id": funcionario.id, "funcionario": funcionario.nome,
            "saldo_minutos": calcular_saldo_banco_horas(db, funcionario_id, data_limite), "lancamentos": linhas,
            "compensacoes": [{c.name: getattr(i, c.name) for c in CompensacaoBancoHoras.__table__.columns} for i in compensacoes],
            "data_demissao": funcionario.data_demissao,
            "saldo_demissao_minutos": calcular_saldo_banco_horas(db, funcionario_id, funcionario.data_demissao) if funcionario.data_demissao else None}


def alertas(db, empresa_id, dias=30, hoje=None):
    hoje = hoje or hoje_local()
    resultado = {"vencidos": [], "proximos_do_vencimento": [], "folgas_sem_cobertura": []}
    for funcionario in db.query(Funcionario).filter_by(empresa_id=empresa_id).order_by(Funcionario.nome):
        for item, _, restante in situacao_lancamentos(db, funcionario.id):
            if item.origem == "folga_compensatoria" and restante:
                resultado["folgas_sem_cobertura"].append(dict(id=item.id, funcionario_id=funcionario.id, funcionario=funcionario.nome,
                    data_referencia=item.data_referencia, data_vencimento=None, minutos_restantes=restante))
            if item.natureza != "credito" or not restante or not item.data_vencimento:
                continue
            categoria = "vencidos" if item.data_vencimento < hoje else "proximos_do_vencimento"
            if item.data_vencimento <= hoje + timedelta(days=dias):
                resultado[categoria].append(dict(id=item.id, funcionario_id=funcionario.id, funcionario=funcionario.nome,
                    data_vencimento=item.data_vencimento, minutos_restantes=restante))
    for itens in resultado.values():
        itens.sort(key=lambda i: (i["data_vencimento"] or i["data_referencia"], i["id"]))
    return resultado


def formatar_saldo(minutos):
    sinal = "+" if minutos > 0 else "-" if minutos < 0 else ""
    horas, resto = divmod(abs(minutos), 60)
    return f"{sinal}{horas:02d}:{resto:02d}"


def complementar_apuracao(db, competencia, resultado):
    """Acrescenta uma visão do ledger; não modifica o snapshot de ponto salvo."""
    from calendar import monthrange
    if competencia.status == "fechada" and competencia.versao_fechamento == 0:
        return resultado  # Nenhuma aplicação retroativa a fechamentos legados.
    inicio = date(competencia.ano, competencia.mes, 1)
    fim = date(competencia.ano, competencia.mes, monthrange(competencia.ano, competencia.mes)[1])
    por_funcionario = {}
    for dia in resultado["marcacoes"]:
        por_funcionario.setdefault(dia["funcionario_id"], []).append(dia)
    for resumo in resultado["resumo"]:
        funcionario = db.get(Funcionario, resumo["funcionario_id"])
        if not funcionario:
            continue
        dias = por_funcionario.get(funcionario.id, [])
        if competencia.status == "fechada":
            habilitado = any(d.get("banco_horas_regra") for d in dias)
        else:
            vinculos = [escala_no_dia(db, funcionario, date.fromisoformat(d["data"])) for d in dias]
            habilitado = any(e and e.usa_banco_horas for e in vinculos) or bool(funcionario.escala and funcionario.escala.usa_banco_horas)
        if not habilitado:
            continue
        itens = [i for i, _, _ in situacao_lancamentos(db, funcionario.id, fim) if i.data_referencia >= inicio]
        resumo["banco_horas"] = {
            "consolidado": competencia.status == "fechada",
            "saldo_anterior_minutos": calcular_saldo_banco_horas(db, funcionario.id, inicio - timedelta(days=1)),
            "creditos_competencia_minutos": sum(i.minutos for i in itens if i.natureza == "credito"),
            "debitos_competencia_minutos": sum(i.minutos for i in itens if i.natureza == "debito"),
            "saldo_final_minutos": calcular_saldo_banco_horas(db, funcionario.id, fim),
        }
        if funcionario.data_demissao and funcionario.data_demissao <= fim:
            resumo["banco_horas"].update(data_demissao=funcionario.data_demissao.isoformat(),
                saldo_demissao_minutos=calcular_saldo_banco_horas(db, funcionario.id, funcionario.data_demissao))
    return resultado
