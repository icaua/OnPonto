"""Interpretação explícita de intervalo; horários de evidência nunca são alterados."""
from dataclasses import replace


def preparar(regra, marcacao):
    if regra is None or regra.tipo_intervalo is None:
        return marcacao, None, None
    campos = ("entrada", "saida_almoco", "retorno_almoco", "saida")
    origens = {c:"real" if getattr(marcacao,c) is not None else None for c in campos}
    if marcacao.batidas_originais:
        import json
        from collections import Counter
        try:
            brutas=json.loads(marcacao.batidas_originais)
        except (ValueError,TypeError):
            brutas=None
        if isinstance(brutas,list):
            disponiveis=Counter(str(h)[:5] for h in brutas)
            for campo in campos:
                hora=getattr(marcacao,campo)
                if hora is None: continue
                chave=hora.isoformat()[:5]
                if disponiveis[chave]: disponiveis[chave]-=1
                else: origens[campo]="corrigido"
    if bool(marcacao.saida_almoco) != bool(marcacao.retorno_almoco):
        return marcacao, origens, "Intervalo incompleto; a pré-assinalação não completa registro parcial."
    if regra.tipo_intervalo == "sem_intervalo":
        if marcacao.saida_almoco or marcacao.retorno_almoco:
            return marcacao, origens, "Há batidas de intervalo em jornada configurada sem intervalo. Revise a regra ou o dia."
        return marcacao, origens, None
    if not marcacao.entrada or not marcacao.saida:
        return marcacao, origens, "Entrada e saída reais são obrigatórias."
    if marcacao.saida_almoco and marcacao.retorno_almoco:
        return marcacao, origens, None
    if regra.registro_intervalo != "pre_assinalado":
        return marcacao, origens, "Intervalo exige batidas reais; não há pré-assinalação configurada."
    inicio, fim = regra.horario_saida_almoco_prevista, regra.horario_retorno_almoco_prevista
    if not inicio or not fim or not marcacao.entrada < inicio < fim < marcacao.saida:
        return marcacao, origens, "Pré-assinalação sem referencial válido dentro da entrada/saída reais."
    origens.update(saida_almoco="pre_assinalado", retorno_almoco="pre_assinalado")
    return replace(marcacao, saida_almoco=inicio, retorno_almoco=fim), origens, None
