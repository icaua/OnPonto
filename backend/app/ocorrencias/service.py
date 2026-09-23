import json
from calendar import monthrange
from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import or_, text

from app.database.models import Competencia, Funcionario, OcorrenciaFuncionario
from app.ocorrencias.schemas import OcorrenciaCreate


def iniciar_escrita(db):
    # Serializa validação + escrita contra outros cadastros/fechamentos SQLite.
    if db.get_bind().dialect.name == "sqlite":
        conexao = db.connection()
        if not conexao.connection.driver_connection.in_transaction:
            db.execute(text("BEGIN IMMEDIATE"))


def consultar(db, funcionario_id=None, empresa_id=None, inicio=None, fim=None, incluir_excluidas=False):
    query = db.query(OcorrenciaFuncionario).join(Funcionario)
    if not incluir_excluidas:
        query = query.filter(OcorrenciaFuncionario.excluido_em.is_(None))
    if funcionario_id is not None:
        query = query.filter(OcorrenciaFuncionario.funcionario_id == funcionario_id)
    if empresa_id is not None:
        query = query.filter(Funcionario.empresa_id == empresa_id)
    if inicio:
        query = query.filter(or_(OcorrenciaFuncionario.data_fim.is_(None), OcorrenciaFuncionario.data_fim >= inicio))
    if fim:
        query = query.filter(OcorrenciaFuncionario.data_inicio <= fim)
    return query.order_by(OcorrenciaFuncionario.data_inicio.desc(), OcorrenciaFuncionario.id.desc()).all()


def validar_fechadas(db, dados):
    funcionario = db.get(Funcionario, dados.funcionario_id)
    if not funcionario:
        raise HTTPException(404, "Funcionário não encontrado.")
    for competencia in db.query(Competencia).filter_by(empresa_id=funcionario.empresa_id, status="fechada"):
        inicio = date(competencia.ano, competencia.mes, 1)
        fim = date(competencia.ano, competencia.mes, monthrange(competencia.ano, competencia.mes)[1])
        if dados.data_inicio <= fim and (dados.data_fim is None or dados.data_fim >= inicio):
            raise HTTPException(409, f"A ocorrência atinge a competência fechada {competencia.mes:02d}/{competencia.ano}. Reabra a competência primeiro.")


def validar_sobreposicao(db, dados, ignorar_id=None):
    for outra in consultar(db, funcionario_id=dados.funcionario_id, inicio=dados.data_inicio, fim=dados.data_fim):
        if outra.id == ignorar_id:
            continue
        if dados.hora_inicio and outra.hora_inicio:
            if dados.hora_inicio >= outra.hora_fim or outra.hora_inicio >= dados.hora_fim:
                continue
        raise HTTPException(409, f"Sobreposição com a ocorrência #{outra.id}. Revise o período antes de salvar.")


def estado(ocorrencia):
    campos = [*OcorrenciaCreate.model_fields, "anexo_caminho", "anexo_nome", "excluido_em"]
    return {campo: valor.isoformat() if hasattr(valor, "isoformat") else valor
            for campo in campos for valor in [getattr(ocorrencia, campo)]}


def auditar(ocorrencia, acao, antes):
    depois = estado(ocorrencia)
    if antes == depois:
        return
    eventos = ocorrencia.historico
    eventos.append({"id": str(uuid4()), "acao": acao, "at": datetime.now(timezone.utc).isoformat(),
                    "actor": "Operador local", "antes": antes, "depois": depois})
    ocorrencia.historico_json = json.dumps(eventos, ensure_ascii=False)


def sincronizar_abertas(db, *periodos):
    from app.competencias.service import sincronizar_status_competencia
    db.flush()
    ids = set()
    for dados in periodos:
        funcionario = db.get(Funcionario, dados.funcionario_id)
        for competencia in db.query(Competencia).filter(Competencia.empresa_id == funcionario.empresa_id, Competencia.status != "fechada"):
            inicio = date(competencia.ano, competencia.mes, 1)
            fim = date(competencia.ano, competencia.mes, monthrange(competencia.ano, competencia.mes)[1])
            if competencia.id not in ids and dados.data_inicio <= fim and (dados.data_fim is None or dados.data_fim >= inicio):
                sincronizar_status_competencia(db, competencia)
                ids.add(competencia.id)
