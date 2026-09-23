import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException


CAMPOS = ("entrada", "saida_almoco", "retorno_almoco", "saida", "status_dia", "conferido", "observacoes")
ROTULOS = dict(zip(CAMPOS, ("Entrada", "Saída para almoço", "Retorno do almoço", "Saída", "Situação", "Conferido", "Observações")))


def estado(marcacao) -> dict:
    resultado = {}
    for campo in CAMPOS:
        valor = getattr(marcacao, campo)
        resultado[campo] = valor.isoformat() if hasattr(valor, "isoformat") else valor
    return resultado


def validar_sequencia(marcacao) -> None:
    horarios = [getattr(marcacao, campo) for campo in CAMPOS[:4] if getattr(marcacao, campo) is not None]
    if any(a >= b for a, b in zip(horarios, horarios[1:])):
        raise HTTPException(status_code=422, detail="A ordem deve ser entrada, saída para almoço, retorno do almoço e saída.")


def registrar_alteracao(marcacao, antes: dict | None) -> None:
    depois = estado(marcacao)
    alteracoes = {campo: {"antes": antes.get(campo) if antes else None, "depois": depois[campo]}
                  for campo in CAMPOS if antes is None or antes.get(campo) != depois[campo]}
    if not alteracoes:
        return
    historico = marcacao.historico
    descricao = "; ".join(
        f"{ROTULOS[campo]}: {mudanca['antes'] if mudanca['antes'] is not None else '—'} → "
        f"{mudanca['depois'] if mudanca['depois'] is not None else '—'}"
        for campo, mudanca in alteracoes.items()
    )
    historico.append({"id": str(uuid4()), "at": datetime.now(timezone.utc).isoformat(),
                      "actor": "Operador local", "description": descricao,
                      "title": "Registro criado" if antes is None else "Registro alterado",
                      "type": "manual", "alteracoes": alteracoes})
    marcacao.historico_json = json.dumps(historico, ensure_ascii=False)
