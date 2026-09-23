from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.database.models import Empresa, Escala, Funcionario, MarcacaoPonto, OcorrenciaFuncionario, LancamentoBancoHoras
from app.funcionarios.historico_escalas import registrar_vinculo_inicial, trocar_vinculo
from app.ocorrencias.service import iniciar_escrita
from app.database.session import get_db
from app.funcionarios.schemas import DatasVinculo, FuncionarioCreate, FuncionarioRead, FuncionarioUpdate


router = APIRouter(prefix="/funcionarios", tags=["Funcionários"])


def validar_escala(
    db: Session,
    empresa_id: int,
    escala_id: int | None,
    *,
    escala_inativa_permitida_id: int | None = None,
) -> None:
    if escala_id is None:
        return
    escala = db.get(Escala, escala_id)
    if not escala:
        raise HTTPException(status_code=404, detail="Escala não encontrada.")
    if escala.empresa_id != empresa_id:
        raise HTTPException(status_code=400, detail="Escala não pertence à empresa do funcionário.")
    if not escala.ativa and escala.id != escala_inativa_permitida_id:
        raise HTTPException(status_code=400, detail="Não é possível vincular uma escala inativa.")


@router.get("", response_model=list[FuncionarioRead])
def listar_funcionarios(
    empresa_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Funcionario]:
    query = db.query(Funcionario)
    if empresa_id:
        query = query.filter(Funcionario.empresa_id == empresa_id)
    return query.order_by(Funcionario.nome.asc()).all()


@router.post("", response_model=FuncionarioRead, status_code=status.HTTP_201_CREATED)
def criar_funcionario(payload: FuncionarioCreate, db: Session = Depends(get_db)) -> Funcionario:
    iniciar_escrita(db)
    if not db.get(Empresa, payload.empresa_id):
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    validar_escala(db, payload.empresa_id, payload.escala_id)

    funcionario = Funcionario(**payload.model_dump())
    db.add(funcionario)
    try:
        db.flush()
        registrar_vinculo_inicial(db, funcionario)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Código já usado nesta empresa.") from exc
    db.refresh(funcionario)
    return funcionario


@router.get("/{funcionario_id}", response_model=FuncionarioRead)
def obter_funcionario(funcionario_id: int, db: Session = Depends(get_db)) -> Funcionario:
    funcionario = db.get(Funcionario, funcionario_id)
    if not funcionario:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")
    return funcionario


@router.patch("/{funcionario_id}", response_model=FuncionarioRead)
def atualizar_funcionario(
    funcionario_id: int,
    payload: FuncionarioUpdate,
    db: Session = Depends(get_db),
) -> Funcionario:
    iniciar_escrita(db)
    funcionario = db.get(Funcionario, funcionario_id)
    if not funcionario:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")

    dados = payload.model_dump(exclude_unset=True)
    try:
        DatasVinculo(data_admissao=dados.get("data_admissao", funcionario.data_admissao),
                    data_demissao=dados.get("data_demissao", funcionario.data_demissao))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="A data de demissão não pode ser anterior à data de admissão.") from exc
    if "empresa_id" in dados and not db.get(Empresa, dados["empresa_id"]):
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    empresa_id = dados.get("empresa_id", funcionario.empresa_id)
    if empresa_id != funcionario.empresa_id and db.query(LancamentoBancoHoras.id).filter_by(funcionario_id=funcionario.id).first():
        raise HTTPException(409, "Funcionário com histórico de banco de horas não pode ser transferido para outra empresa.")
    if empresa_id != funcionario.empresa_id and db.query(OcorrenciaFuncionario.id).filter_by(funcionario_id=funcionario.id).first():
        raise HTTPException(409, "Funcionário com histórico de ocorrências não pode ser transferido para outra empresa.")
    if empresa_id != funcionario.empresa_id and db.query(MarcacaoPonto.id).filter_by(funcionario_id=funcionario.id).first():
        raise HTTPException(409, "Funcionário com histórico de marcações não pode ser transferido para outra empresa.")
    escala_id = dados.get("escala_id", funcionario.escala_id)
    validar_escala(
        db,
        empresa_id,
        escala_id,
        escala_inativa_permitida_id=funcionario.escala_id,
    )

    if escala_id != funcionario.escala_id:
        trocar_vinculo(db, funcionario, escala_id)
    for campo, valor in dados.items():
        setattr(funcionario, campo, valor)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Código já usado nesta empresa.") from exc
    db.refresh(funcionario)
    return funcionario
