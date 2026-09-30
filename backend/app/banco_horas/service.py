"""Serviços transacionais do ledger. O chamador é responsável pelo commit."""
import json
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException

from app.banco_horas.politica import hoje_local, validar_prazo, vencimento_credito
from app.banco_horas.regras import politica_da_escala, ciclo
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
        politica = politica_da_escala(escala)
        prazo = politica.ciclo_dias if politica else validar_prazo(competencia.empresa)
        inicio, fim = ciclo(politica, referencia) if politica else (None, None)
        credito = dia.get("extra_minutos") or 0
        if competencia.empresa.feriado_entra_banco:
            credito += dia.get("horas_feriado_minutos") or 0
        debito = dia.get("atraso_minutos") or 0
        if politica:
            if dia.get("extra_banco_minutos") is None or dia.get("debito_banco_minutos") is None:
                raise HTTPException(409, "A distribuição da política não foi calculada. Revise a apuração.")
            credito = dia["extra_banco_minutos"]
            debito = dia["debito_banco_minutos"] - dia.get("minutos_folga_compensatoria", 0)
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
                data_vencimento=(fim or vencimento_credito(referencia, prazo)) if natureza == "credito" else None,
                ciclo_inicio=inicio, ciclo_fim=fim,
                politica_aplicada_json=json.dumps(dia.get("politica_horas_aplicada"), ensure_ascii=False) if politica else None,
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
            regra = json.loads(item.politica_aplicada_json)["politica"] if item.politica_aplicada_json else None
            if item.id in ids and restante and not (regra and regra["permite_saldo_negativo"]):
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
            # Ciclos explícitos não consomem saldo legado nem saldo de outro ciclo.
            # Transportes e quitações exigem ajustes documentados, sem baixa automática.
            if (item.ciclo_inicio, item.ciclo_fim) != (outro.ciclo_inicio, outro.ciclo_fim):
                continue
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
    escala = escala_no_dia(db, funcionario, payload.data_referencia) or funcionario.escala
    politica = politica_da_escala(escala)
    inicio, fim = ciclo(politica, payload.data_referencia) if politica else (None, None)
    regra_json = json.dumps({"escala_id": escala.id, "politica": politica.model_dump(mode="json")}) if politica else None
    escala_id = escala.id if escala else None
    prazo = politica.ciclo_dias if politica and politica.percentual_banco else None
    if payload.lancamento_referencia_id is not None:
        referencia = db.get(LancamentoBancoHoras, payload.lancamento_referencia_id)
        if not referencia or referencia.funcionario_id != funcionario.id or referencia.status != "ativo":
            raise HTTPException(422, "Selecione um lançamento ativo deste funcionário como referência do ajuste.")
        inicio, fim = referencia.ciclo_inicio, referencia.ciclo_fim
        regra_json, escala_id = referencia.politica_aplicada_json, referencia.escala_origem_id
        prazo = referencia.prazo_compensacao_aplicado_dias
        if inicio and not inicio <= payload.data_referencia <= fim:
            raise HTTPException(422, "A data de referência deve pertencer ao ciclo selecionado. A data do lançamento registra quando o ajuste foi feito.")
    if payload.natureza == "credito" and not prazo:
        prazo = validar_prazo(funcionario.empresa)
    item = LancamentoBancoHoras(**payload.model_dump(), empresa_id=funcionario.empresa_id,
        origem="ajuste_manual", escala_origem_id=escala_id,
        ciclo_inicio=inicio, ciclo_fim=fim,
        politica_aplicada_json=regra_json,
        data_lancamento=hoje_local(), prazo_compensacao_aplicado_dias=prazo,
        data_vencimento=(fim or vencimento_credito(payload.data_referencia, prazo)) if payload.natureza == "credito" else None,
        feriado_entra_banco_aplicado=funcionario.empresa.feriado_entra_banco)
    db.add(item); db.flush()
    reconciliar(db, funcionario.id, "Novo ajuste manual")
    validar_saldos_permitidos(db, [item])
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
        regra_json = linha.pop("politica_aplicada_json")
        linha["politica_aplicada"] = json.loads(regra_json) if regra_json else None
        linha.update(minutos_compensados=consumidos, minutos_restantes=restantes, saldo_acumulado_minutos=acumulado)
        linhas.append(linha)
    ids = [i["id"] for i in linhas]
    compensacoes = db.query(CompensacaoBancoHoras).filter(
        (CompensacaoBancoHoras.credito_id.in_(ids)) | (CompensacaoBancoHoras.debito_id.in_(ids))).order_by(CompensacaoBancoHoras.id).all()
    return {"funcionario_id": funcionario.id, "funcionario": funcionario.nome,
            "saldo_minutos": calcular_saldo_banco_horas(db, funcionario_id, data_limite), "lancamentos": linhas,
            "compensacoes": [{c.name: getattr(i, c.name) for c in CompensacaoBancoHoras.__table__.columns} for i in compensacoes],
            "tratamentos_pendentes": tratamentos_pendentes(db, funcionario, data_limite or hoje_local()),
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
            "compensados_minutos": sum(consumidos for i, consumidos, _ in situacao_lancamentos(db, funcionario.id, fim)
                                       if i.natureza == "debito" and i.data_referencia >= inicio),
            "tratamentos_pendentes": tratamentos_pendentes(db, funcionario, fim),
        }
        if funcionario.data_demissao and funcionario.data_demissao <= fim:
            resumo["banco_horas"].update(data_demissao=funcionario.data_demissao.isoformat(),
                saldo_demissao_minutos=calcular_saldo_banco_horas(db, funcionario.id, funcionario.data_demissao))
    return resultado


def validar_saldos_permitidos(db, gerados):
    for funcionario_id in {i.funcionario_id for i in gerados}:
        situacao = situacao_lancamentos(db, funcionario_id)
        for item in (i for i in gerados if i.funcionario_id == funcionario_id and i.politica_aplicada_json):
            regra = json.loads(item.politica_aplicada_json)["politica"]
            if regra["permite_saldo_negativo"]:
                continue
            saldo = sum(restante if i.natureza == "credito" else -restante for i, _, restante in situacao
                        if (i.ciclo_inicio, i.ciclo_fim) == (item.ciclo_inicio, item.ciclo_fim))
            if saldo < 0:
                raise HTTPException(409, "Esta política não permite saldo negativo no ciclo. Revise os débitos antes de confirmar.")


def bloqueios_saldo_projetado(db, resultado):
    """Mesma restrição do fechamento, projetada sem inserir lançamentos."""
    grupos = {}
    for dia in resultado["marcacoes"]:
        aplicada = dia.get("politica_horas_aplicada")
        if not aplicada or dia.get("extra_banco_minutos") is None or not dia.get("ciclo_inicio"):
            continue
        chave = (dia["funcionario_id"], dia["ciclo_inicio"], dia["ciclo_fim"])
        grupo = grupos.setdefault(chave, {"delta": 0, "restrito": False})
        grupo["delta"] += dia["extra_banco_minutos"] - dia["debito_banco_minutos"]
        grupo["restrito"] |= not aplicada["politica"]["permite_saldo_negativo"]
    motivos = []
    for (funcionario_id, inicio, fim), grupo in grupos.items():
        if not grupo["restrito"]:
            continue
        saldo = sum(restante if i.natureza == "credito" else -restante
                    for i, _, restante in situacao_lancamentos(db, funcionario_id)
                    if i.ciclo_inicio == date.fromisoformat(inicio) and i.ciclo_fim == date.fromisoformat(fim))
        if saldo + grupo["delta"] < 0:
            motivos.append(f"Funcionário #{funcionario_id}: saldo projetado negativo no ciclo {inicio} a {fim}; a política não permite esse saldo.")
    return motivos


def tratamentos_pendentes(db, funcionario, corte):
    """Indicações para decisão/folha; nunca quita, transporta ou calcula reais."""
    grupos = {}
    desligado = bool(funcionario.data_demissao and funcionario.data_demissao <= corte)
    for item, _, restante in situacao_lancamentos(db, funcionario.id, min(corte, funcionario.data_demissao) if desligado else corte):
        if not restante or not item.politica_aplicada_json or not item.ciclo_fim:
            continue
        if not desligado and item.ciclo_fim >= corte:
            continue
        politica = json.loads(item.politica_aplicada_json)["politica"]
        chave = (item.ciclo_inicio, item.ciclo_fim, json.dumps(politica, sort_keys=True), item.natureza)
        grupo = grupos.setdefault(chave, {"evento": "desligamento" if desligado else "fim_ciclo",
            "ciclo_inicio": item.ciclo_inicio.isoformat(), "ciclo_fim": item.ciclo_fim.isoformat(),
            "natureza": item.natureza, "minutos": 0, "lancamentos_ids": [], "politica": politica})
        grupo["minutos"] += restante
        grupo["lancamentos_ids"].append(item.id)
    resultado = []
    for grupo in grupos.values():
        politica = grupo.pop("politica")
        sufixo = "credor" if grupo["natureza"] == "credito" else "devedor"
        grupo["tratamento"] = politica[grupo["evento"] + "_" + sufixo]
        grupo["adicional_percentual"] = politica["adicional_saldo_percentual"] if sufixo == "credor" else None
        grupo["requer_confirmacao"] = True
        resultado.append(grupo)
    return resultado
