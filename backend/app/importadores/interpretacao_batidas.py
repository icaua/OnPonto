from __future__ import annotations

from typing import Any


CAMPOS_HORARIO = ("entrada", "saida_almoco", "retorno_almoco", "saida")


def interpretar_batidas(horarios: list[str]) -> dict[str, Any]:
    """Recebe uma lista de horários ('HH:MM') já ordenada e devolve
    entrada/saida_almoco/retorno_almoco/saida/status/status_dia/observacoes.

    Regra única para todos os adaptadores: 4 horários = normal; 2 = pendente
    (só entrada/saída); 1 = pendente (só entrada); qualquer outra quantidade
    (0, 3 ou mais de 4) = pendente sem preencher nenhum campo — nunca se
    adivinha qual par de horários corresponde a qual evento.
    """

    resultado: dict[str, Any] = {campo: None for campo in CAMPOS_HORARIO}
    quantidade = len(horarios)

    if quantidade == 4:
        resultado.update(zip(CAMPOS_HORARIO, horarios))
        return {**resultado, "status": "normal", "status_dia": "normal", "observacoes": None}

    if quantidade == 2:
        resultado["entrada"], resultado["saida"] = horarios
        return {
            **resultado,
            "status": "pendente_conferencia",
            "status_dia": "normal",
            "observacoes": "Apenas duas marcações encontradas",
        }

    if quantidade == 1:
        resultado["entrada"] = horarios[0]
        return {
            **resultado,
            "status": "pendente_conferencia",
            "status_dia": "normal",
            "observacoes": "Apenas uma marcação encontrada",
        }

    if quantidade == 3:
        return {
            **resultado,
            "status": "pendente_conferencia",
            "status_dia": "normal",
            "observacoes": "Quantidade ímpar de marcações",
        }

    if quantidade == 0:
        return {
            **resultado,
            "status": "pendente",
            "status_dia": "normal",
            "observacoes": "Sem marcações",
        }

    return {
        **resultado,
        "status": "pendente_conferencia",
        "status_dia": "normal",
        "observacoes": "Mais de quatro marcações encontradas",
    }
