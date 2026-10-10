"""Adapta testes funcionais sequenciais ao contrato de revisão HTTP.

Testes de concorrência enviam os tokens capturados diretamente, sem este helper.
"""
import json
import re
from urllib.request import urlopen


def com_revisao(base, metodo, caminho, payload):
    if payload is None or "revisao" in payload:
        return payload
    if metodo == "POST" and caminho == "/importadores/confirmar" and "revisao_previa" not in payload:
        with urlopen(base + "/importadores/" + str(payload["arquivo_id"]) + "/previa", timeout=10) as resposta:
            atual=json.load(resposta)
        return {**payload,"revisao_previa":atual["revisao_previa"]}
    match = re.fullmatch(r"/marcacoes/(\d+)", caminho)
    if metodo == "PATCH" and match:
        with urlopen(base + caminho, timeout=10) as resposta:
            atual = json.load(resposta)
        return {**payload, "revisao": atual["revisao"]}
    if metodo == "POST" and caminho == "/marcacoes":
        with urlopen(base + "/marcacoes?competencia_id=" + str(payload["competencia_id"]), timeout=10) as resposta:
            existentes = json.load(resposta)
        atual = next((m for m in existentes if m["funcionario_id"] == payload["funcionario_id"] and m["data"] == payload["data"]), None)
        if atual:
            return {**payload, "revisao": atual["revisao"]}
    return payload
