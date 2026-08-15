#!/usr/bin/env python3
"""Prepara cadastros fictícios para uma demonstração local do On Ponto."""

from __future__ import annotations

import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.exc import IntegrityError  # noqa: E402

from app.database import models  # noqa: E402,F401
from app.database.migrations import aplicar_migracoes_compativeis  # noqa: E402
from app.database.models import Competencia, Empresa, Funcionario  # noqa: E402
from app.database.session import Base, SessionLocal, engine  # noqa: E402


EMPRESA_NOME = "Empresa Demonstração"
EMPRESA_MARCADOR = "onponto-demo-v1"
EMPRESA_OBSERVACOES = (
    "Dados exclusivamente fictícios para demonstração do On Ponto. "
    f"Identificador: {EMPRESA_MARCADOR}."
)
COMPETENCIA_MES = 7
COMPETENCIA_ANO = 2026
FUNCIONARIOS_DEMO = (
    ("F001", "Alice Teste"),
    ("F002", "Bruno Teste"),
)


class ConflitoSeed(RuntimeError):
    """Impede que o seed altere ou se misture a cadastros do usuário."""


@dataclass
class ResultadoSeed:
    criado: list[str]
    reutilizado: list[str]


def _normalizar_texto(valor: str | None) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
    return re.sub(r"\s+", " ", texto).strip().casefold()


def _empresa_demo(db, resultado: ResultadoSeed) -> Empresa:
    empresas = db.query(Empresa).order_by(Empresa.id).all()
    com_marcador = [
        empresa
        for empresa in empresas
        if EMPRESA_MARCADOR in str(empresa.observacoes or "").casefold()
    ]
    com_nome = [
        empresa
        for empresa in empresas
        if _normalizar_texto(empresa.nome) == _normalizar_texto(EMPRESA_NOME)
    ]

    if len(com_marcador) > 1 or len(com_nome) > 1:
        raise ConflitoSeed(
            "Há mais de uma empresa que parece pertencer à demonstração. "
            "Revise os cadastros manualmente; nada foi alterado."
        )

    if com_marcador:
        empresa = com_marcador[0]
        if _normalizar_texto(empresa.nome) != _normalizar_texto(EMPRESA_NOME):
            raise ConflitoSeed(
                f'A empresa marcada com "{EMPRESA_MARCADOR}" foi renomeada. '
                "O seed não restaura nem sobrescreve dados existentes."
            )
        if com_nome and com_nome[0].id != empresa.id:
            raise ConflitoSeed(
                f'Já existe outra empresa chamada "{EMPRESA_NOME}". '
                "O seed não pode escolher com segurança; nada foi alterado."
            )
        resultado.reutilizado.append(f'empresa "{empresa.nome}" (id {empresa.id})')
        return empresa

    if com_nome:
        raise ConflitoSeed(
            f'Já existe uma empresa chamada "{EMPRESA_NOME}" sem o marcador do seed. '
            "Para proteger dados do usuário, nenhum cadastro foi criado."
        )

    empresa = Empresa(
        nome=EMPRESA_NOME,
        cnpj=None,
        jornada_seg_sex_horas=8,
        jornada_sabado_horas=4,
        tolerancia_atraso_minutos=5,
        tolerancia_extra_minutos=10,
        ativa=True,
        observacoes=EMPRESA_OBSERVACOES,
    )
    db.add(empresa)
    db.flush()
    resultado.criado.append(f'empresa "{empresa.nome}" (id {empresa.id})')
    return empresa


def _validar_funcionarios_existentes(db, empresa: Empresa) -> dict[str, Funcionario]:
    existentes = db.query(Funcionario).filter(Funcionario.empresa_id == empresa.id).all()
    por_codigo: dict[str, list[Funcionario]] = {}
    por_nome: dict[str, list[Funcionario]] = {}
    for funcionario in existentes:
        codigo = _normalizar_texto(funcionario.codigo)
        nome = _normalizar_texto(funcionario.nome)
        if codigo:
            por_codigo.setdefault(codigo, []).append(funcionario)
        if nome:
            por_nome.setdefault(nome, []).append(funcionario)

    reutilizaveis: dict[str, Funcionario] = {}
    for codigo_esperado, nome_esperado in FUNCIONARIOS_DEMO:
        codigo = _normalizar_texto(codigo_esperado)
        nome = _normalizar_texto(nome_esperado)
        candidatos_codigo = por_codigo.get(codigo, [])
        candidatos_nome = por_nome.get(nome, [])

        if len(candidatos_codigo) > 1:
            raise ConflitoSeed(
                f'O código demonstrativo "{codigo_esperado}" aparece mais de uma vez. '
                "Nenhum cadastro foi alterado."
            )
        if candidatos_codigo:
            funcionario = candidatos_codigo[0]
            if _normalizar_texto(funcionario.nome) != nome:
                raise ConflitoSeed(
                    f'O código "{codigo_esperado}" já pertence a "{funcionario.nome}". '
                    "O seed não renomeia funcionários existentes."
                )
            if any(item.id != funcionario.id for item in candidatos_nome):
                raise ConflitoSeed(
                    f'O nome demonstrativo "{nome_esperado}" também pertence a outro cadastro. '
                    "Nenhum cadastro foi alterado."
                )
            reutilizaveis[codigo_esperado] = funcionario
            continue

        if candidatos_nome:
            outro_codigo = candidatos_nome[0].codigo or "sem código"
            raise ConflitoSeed(
                f'O nome demonstrativo "{nome_esperado}" já existe com o código "{outro_codigo}". '
                "O seed não substitui códigos existentes."
            )

    return reutilizaveis


def _funcionarios_demo(
    db,
    empresa: Empresa,
    resultado: ResultadoSeed,
) -> None:
    reutilizaveis = _validar_funcionarios_existentes(db, empresa)
    for codigo, nome in FUNCIONARIOS_DEMO:
        funcionario = reutilizaveis.get(codigo)
        if funcionario:
            resultado.reutilizado.append(
                f'funcionário "{funcionario.nome}" / {funcionario.codigo} (id {funcionario.id})'
            )
            continue

        funcionario = Funcionario(
            empresa_id=empresa.id,
            codigo=codigo,
            nome=nome,
            cargo="Cadastro fictício para demonstração",
            ativo=True,
            observacoes=f"Dado fictício criado pelo seed {EMPRESA_MARCADOR}.",
        )
        db.add(funcionario)
        db.flush()
        resultado.criado.append(
            f'funcionário "{funcionario.nome}" / {funcionario.codigo} (id {funcionario.id})'
        )


def _competencia_demo(db, empresa: Empresa, resultado: ResultadoSeed) -> None:
    competencia = (
        db.query(Competencia)
        .filter(
            Competencia.empresa_id == empresa.id,
            Competencia.mes == COMPETENCIA_MES,
            Competencia.ano == COMPETENCIA_ANO,
        )
        .one_or_none()
    )
    if competencia:
        resultado.reutilizado.append(
            "competência 07/2026 "
            f'(id {competencia.id}, situação preservada: {competencia.status})'
        )
        return

    competencia = Competencia(
        empresa_id=empresa.id,
        mes=COMPETENCIA_MES,
        ano=COMPETENCIA_ANO,
        status="aberta",
        observacoes=f"Competência fictícia criada pelo seed {EMPRESA_MARCADOR}.",
    )
    db.add(competencia)
    db.flush()
    resultado.criado.append(f"competência 07/2026 (id {competencia.id})")


def executar_seed() -> ResultadoSeed:
    Base.metadata.create_all(bind=engine)
    aplicar_migracoes_compativeis(engine)
    resultado = ResultadoSeed(criado=[], reutilizado=[])

    with SessionLocal() as db:
        with db.begin():
            empresa = _empresa_demo(db, resultado)
            _funcionarios_demo(db, empresa, resultado)
            _competencia_demo(db, empresa, resultado)

    return resultado


def main() -> int:
    try:
        resultado = executar_seed()
    except ConflitoSeed as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        return 2
    except IntegrityError as erro:
        print(
            "ERRO: O banco recusou o seed por conflito de integridade; nada foi criado. "
            "Revise os cadastros demonstrativos e tente novamente.",
            file=sys.stderr,
        )
        print(f"Detalhe técnico: {erro.orig}", file=sys.stderr)
        return 2
    except Exception as erro:  # pragma: no cover - proteção do comando interativo
        print(f"ERRO: Não foi possível preparar a demonstração: {erro}", file=sys.stderr)
        return 1

    print("Seed de demonstração concluído.")
    for item in resultado.criado:
        print(f"CRIADO: {item}")
    for item in resultado.reutilizado:
        print(f"REUTILIZADO: {item}")
    print(
        f"Resumo: {len(resultado.criado)} criado(s), "
        f"{len(resultado.reutilizado)} reutilizado(s)."
    )
    print("O código X999 permanece sem cadastro para demonstrar o tratamento de divergências.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
