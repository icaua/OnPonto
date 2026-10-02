"""Validação do uso de batidas desconsideradas, sem modificar a origem."""
import json
from collections import Counter


CAMPOS_HORARIO = ("entrada", "saida_almoco", "retorno_almoco", "saida")


def desconsideradas_em_uso(marcacao, decisoes=None):
    """Compara por minuto, como a edição, preservando duplicatas por índice.

    Uma duplicata pode ser desconsiderada se outra batida do mesmo minuto
    continuar disponível para o campo. Correções manuais de horário continuam
    permitidas; apenas o uso simultâneo de um horário desconsiderado é conflito.
    """
    try:
        brutas = json.loads(marcacao.batidas_originais or "[]")
    except (ValueError, TypeError):
        return False
    if not isinstance(brutas, list):
        return False
    decisoes = marcacao.batidas_desconsideradas if decisoes is None else decisoes
    indices = {item["indice"] for item in decisoes}
    restantes = Counter(str(hora)[:5] for i, hora in enumerate(brutas) if i not in indices)
    descartadas = {str(hora)[:5] for i, hora in enumerate(brutas) if i in indices}
    usados = Counter(str(getattr(marcacao, campo))[:5] for campo in CAMPOS_HORARIO if getattr(marcacao, campo))
    return any(usados[hora] > restantes[hora] for hora in descartadas)
