"""Conversão explícita do armazenamento para valores do domínio."""
from dataclasses import fields,MISSING
from copy import deepcopy

from app.dominio.contratos import FuncionarioDoDia,MarcacoesDoDia,RegraVigente,Ocorrencia,OcorrenciasDoDia


def regra(escala):
    if escala is None: return None
    return RegraVigente(**{f.name:deepcopy(getattr(escala,f.name,f.default if f.default is not MISSING else None)) for f in fields(RegraVigente)})


def funcionario(funcionario):
    return FuncionarioDoDia(id=funcionario.id,nome=funcionario.nome,
        nome_exibicao=getattr(funcionario,"nome_exibicao",None),
        data_admissao=funcionario.data_admissao,data_demissao=funcionario.data_demissao,
        escala=regra(funcionario.escala))


def marcacoes(marcacao):
    return MarcacoesDoDia(**{f.name:getattr(marcacao,f.name) for f in fields(MarcacoesDoDia)})


def ocorrencias(itens):
    return OcorrenciasDoDia(tuple(Ocorrencia(**{f.name:getattr(o,f.name) for f in fields(Ocorrencia)}) for o in itens))
