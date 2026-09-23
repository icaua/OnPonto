from datetime import datetime
import json
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.competencias.schemas import (
    CompetenciaAcaoRead,
    CompetenciaCreate,
    CompetenciaRead,
    CompetenciaUpdate,
    FechamentoCompetenciaRequest,
)
from app.competencias.service import (
    contar_marcacoes,
    contar_pendencias_operacionais,
    exigir_competencia_editavel,
    mensagem_pendencias,
    sincronizar_status_competencia,
)
from app.database.models import ArquivoRecebido, Competencia, Empresa, MarcacaoPonto
from app.database.session import get_db
from app.apuracao.service import apurar_competencia
from app.ocorrencias.service import iniciar_escrita
from app.banco_horas.service import gerar_lancamentos, reconciliar, estornar_competencia, validar_cobertura_folgas


router = APIRouter(prefix="/competencias", tags=["Competências"])
FUSO_HORARIO_LOCAL = ZoneInfo("America/Sao_Paulo")


@router.get("", response_model=list[CompetenciaRead])
def listar_competencias(
    empresa_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Competencia]:
    query = db.query(Competencia)
    if empresa_id:
        query = query.filter(Competencia.empresa_id == empresa_id)
    return query.order_by(Competencia.ano.desc(), Competencia.mes.desc()).all()


@router.post("", response_model=CompetenciaRead, status_code=status.HTTP_201_CREATED)
def criar_competencia(payload: CompetenciaCreate, db: Session = Depends(get_db)) -> Competencia:
    if not db.get(Empresa, payload.empresa_id):
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")

    competencia = Competencia(**payload.model_dump(), status="aberta", data_fechamento=None)
    db.add(competencia)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Competência já cadastrada para esta empresa.") from exc
    db.refresh(competencia)
    return competencia


@router.get("/{competencia_id}", response_model=CompetenciaRead)
def obter_competencia(competencia_id: int, db: Session = Depends(get_db)) -> Competencia:
    competencia = db.get(Competencia, competencia_id)
    if not competencia:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")
    return competencia


@router.patch("/{competencia_id}", response_model=CompetenciaRead)
def atualizar_competencia(
    competencia_id: int,
    payload: CompetenciaUpdate,
    db: Session = Depends(get_db),
) -> Competencia:
    competencia = db.get(Competencia, competencia_id)
    if not competencia:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")
    exigir_competencia_editavel(competencia)

    dados = payload.model_dump(exclude_unset=True)
    if "empresa_id" in dados and not db.get(Empresa, dados["empresa_id"]):
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")

    estrutura_alterada = any(
        campo in dados and dados[campo] != getattr(competencia, campo)
        for campo in ("empresa_id", "mes", "ano")
    )
    if estrutura_alterada:
        possui_dados = (
            db.query(MarcacaoPonto.id)
            .filter(MarcacaoPonto.competencia_id == competencia.id)
            .first()
            is not None
            or db.query(ArquivoRecebido.id)
            .filter(ArquivoRecebido.competencia_id == competencia.id)
            .first()
            is not None
        )
        if possui_dados:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Empresa, mês e ano não podem ser alterados depois que a "
                    "competência possui marcações ou arquivos."
                ),
            )

    for campo, valor in dados.items():
        setattr(competencia, campo, valor)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Competência já cadastrada para esta empresa.") from exc
    db.refresh(competencia)
    return competencia


@router.post("/{competencia_id}/fechar", response_model=CompetenciaAcaoRead)
def fechar_competencia(
    competencia_id: int,
    payload: FechamentoCompetenciaRequest,
    db: Session = Depends(get_db),
) -> dict:
    iniciar_escrita(db)
    competencia = db.get(Competencia, competencia_id)
    if not competencia:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")
    db.refresh(competencia)
    if competencia.status == "fechada":
        raise HTTPException(status_code=409, detail="A competência já está fechada.")

    total_pendencias = sincronizar_status_competencia(
        db,
        competencia,
        gerar_calendario=True,
    )
    total_marcacoes = contar_marcacoes(db, competencia.id)
    fechamento_excepcional = competencia.status != "conferida"

    if fechamento_excepcional and not payload.confirmar_pendencias:
        if total_pendencias:
            codigo = "competencia_com_pendencias"
            mensagem = mensagem_pendencias(total_pendencias)
        elif total_marcacoes == 0:
            codigo = "competencia_sem_registros"
            mensagem = "A competência não possui registros processados para fechamento."
        else:
            codigo = "competencia_nao_conferida"
            mensagem = "A competência ainda não está conferida."
        # O calendário gerado ao tentar fechar é informação válida da
        # competência e precisa continuar visível mesmo quando o fechamento é
        # recusado por pendências.
        db.commit()
        raise HTTPException(
            status_code=409,
            detail={
                "codigo": codigo,
                "mensagem": mensagem,
                "total_pendencias": total_pendencias,
            },
        )

    try:
        resultado = apurar_competencia(db, competencia.id, gerar_calendario=False, incluir_banco=False)
        competencia.data_fechamento = datetime.now(FUSO_HORARIO_LOCAL).date()
        competencia.versao_fechamento += 1
        gerados = gerar_lancamentos(db, competencia, resultado)
        for funcionario_id in sorted({item.funcionario_id for item in gerados}):
            reconciliar(db, funcionario_id, "Fechamento de competência")
        validar_cobertura_folgas(db, gerados)
        resultado["competencia"]["status"] = "fechada"
        resultado["competencia"]["versao_fechamento"] = competencia.versao_fechamento
        competencia.apuracao_fechada = json.dumps(resultado, ensure_ascii=False)
        competencia.status = "fechada"
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(competencia)

    if fechamento_excepcional:
        if total_pendencias:
            mensagem = (
                f"Competência fechada excepcionalmente com {total_pendencias} "
                f"{'registro pendente' if total_pendencias == 1 else 'registros pendentes'}."
            )
        elif total_marcacoes == 0:
            mensagem = "Competência fechada excepcionalmente sem registros processados."
        else:
            mensagem = "Competência fechada excepcionalmente antes da conclusão da conferência."
    else:
        mensagem = "Competência fechada."

    return {
        "id": competencia.id,
        "status": competencia.status,
        "data_fechamento": competencia.data_fechamento,
        "total_pendencias": total_pendencias,
        "fechamento_excepcional": fechamento_excepcional,
        "mensagem": mensagem,
    }


@router.post("/{competencia_id}/reabrir", response_model=CompetenciaAcaoRead)
def reabrir_competencia(
    competencia_id: int,
    db: Session = Depends(get_db),
) -> dict:
    iniciar_escrita(db)
    competencia = db.get(Competencia, competencia_id)
    if not competencia:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")
    db.refresh(competencia)
    if competencia.status != "fechada":
        raise HTTPException(status_code=409, detail="A competência não está fechada.")

    try:
        estornar_competencia(db, competencia)
        competencia.status = "aberta"
        competencia.apuracao_fechada = None
        total_pendencias = contar_pendencias_operacionais(
            db, competencia.id, gerar_calendario=True,
        )
        total_marcacoes = contar_marcacoes(db, competencia.id)
        competencia.status = "em_conferencia" if total_marcacoes else "aberta"
        competencia.data_fechamento = None
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(competencia)

    return {
        "id": competencia.id,
        "status": competencia.status,
        "data_fechamento": competencia.data_fechamento,
        "total_pendencias": total_pendencias,
        "fechamento_excepcional": False,
        "mensagem": "Competência reaberta.",
    }
