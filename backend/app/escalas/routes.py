from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database.models import Empresa, Escala, Funcionario, HistoricoVinculoEscala, LancamentoBancoHoras
from app.banco_horas.politica import validar_prazo
from app.banco_horas.service import calcular_saldo_banco_horas
from app.ocorrencias.service import iniciar_escrita
from app.database.session import get_db
from app.escalas.schemas import EscalaBase, EscalaCreate, EscalaRead, EscalaUpdate


router = APIRouter(prefix="/escalas", tags=["Escalas"])


def obter_escala_ou_404(db: Session, escala_id: int) -> Escala:
    escala = db.get(Escala, escala_id)
    if not escala:
        raise HTTPException(status_code=404, detail="Escala não encontrada.")
    return escala


def validar_empresa(db: Session, empresa_id: int) -> None:
    if not db.get(Empresa, empresa_id):
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")


@router.get("", response_model=list[EscalaRead])
def listar_escalas(
    empresa_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Escala]:
    query = db.query(Escala)
    if empresa_id is not None:
        query = query.filter(Escala.empresa_id == empresa_id)
    return query.order_by(Escala.nome.asc(), Escala.id.asc()).all()


@router.post("", response_model=EscalaRead, status_code=status.HTTP_201_CREATED)
def criar_escala(payload: EscalaCreate, db: Session = Depends(get_db)) -> Escala:
    iniciar_escrita(db)
    validar_empresa(db, payload.empresa_id)
    if payload.usa_banco_horas:
        validar_prazo(db.get(Empresa, payload.empresa_id))
    escala = Escala(**payload.model_dump())
    db.add(escala)
    db.commit()
    db.refresh(escala)
    return escala


@router.get("/{escala_id}", response_model=EscalaRead)
def obter_escala(escala_id: int, db: Session = Depends(get_db)) -> Escala:
    return obter_escala_ou_404(db, escala_id)


def atualizar(
    escala_id: int,
    payload: EscalaUpdate,
    db: Session,
) -> Escala:
    iniciar_escrita(db)
    escala = obter_escala_ou_404(db, escala_id)
    dados = payload.model_dump(exclude_unset=True)
    dados_completos = {
        campo: dados.get(campo, getattr(escala, campo))
        for campo in EscalaBase.model_fields
    }
    try:
        validados = EscalaBase.model_validate(dados_completos)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(include_context=False),
        ) from exc
    validar_empresa(db, validados.empresa_id)
    if validados.usa_banco_horas:
        validar_prazo(db.get(Empresa, validados.empresa_id))
    if escala.usa_banco_horas and not validados.usa_banco_horas:
        for funcionario in escala.funcionarios:
            if calcular_saldo_banco_horas(db, funcionario.id) != 0:
                raise HTTPException(409, "Não é possível desativar o banco de horas nesta escala: existem funcionários com saldo pendente. Zere o saldo (compensação ou ajuste manual) antes de desativar.")
    tem_historico = db.query(HistoricoVinculoEscala.id).filter_by(escala_id=escala.id).first()
    if validados.empresa_id != escala.empresa_id and tem_historico:
        raise HTTPException(409, "Escala com histórico de vínculos não pode ser transferida para outra empresa.")

    if validados.empresa_id != escala.empresa_id and escala.funcionarios:
        raise HTTPException(
            status_code=400,
            detail="Não é possível mover uma escala que possui funcionários vinculados.",
        )
    for campo, valor in validados.model_dump().items():
        setattr(escala, campo, valor)
    db.commit()
    db.refresh(escala)
    return escala


@router.put("/{escala_id}", response_model=EscalaRead)
def atualizar_escala(
    escala_id: int,
    payload: EscalaUpdate,
    db: Session = Depends(get_db),
) -> Escala:
    return atualizar(escala_id, payload, db)


@router.patch("/{escala_id}", response_model=EscalaRead, include_in_schema=False)
def atualizar_escala_parcial(
    escala_id: int,
    payload: EscalaUpdate,
    db: Session = Depends(get_db),
) -> Escala:
    return atualizar(escala_id, payload, db)


@router.delete("/{escala_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_escala(escala_id: int, db: Session = Depends(get_db)) -> Response:
    iniciar_escrita(db)
    escala = obter_escala_ou_404(db, escala_id)
    vinculados = (
        db.query(Funcionario).filter(Funcionario.escala_id == escala.id).count()
    )
    tem_historico = db.query(HistoricoVinculoEscala.id).filter_by(escala_id=escala.id).first()
    tem_banco = db.query(LancamentoBancoHoras.id).filter_by(escala_origem_id=escala.id).first()
    if vinculados or tem_historico or tem_banco:
        escala.ativa = False
    else:
        db.delete(escala)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
