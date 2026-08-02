from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import Empresa, Funcionario
from app.database.session import get_db
from app.funcionarios.schemas import FuncionarioCreate, FuncionarioRead, FuncionarioUpdate


router = APIRouter(prefix="/funcionarios", tags=["Funcionários"])


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
    if not db.get(Empresa, payload.empresa_id):
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")

    funcionario = Funcionario(**payload.model_dump())
    db.add(funcionario)
    try:
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
    funcionario = db.get(Funcionario, funcionario_id)
    if not funcionario:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")

    dados = payload.model_dump(exclude_unset=True)
    if "empresa_id" in dados and not db.get(Empresa, dados["empresa_id"]):
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")

    for campo, valor in dados.items():
        setattr(funcionario, campo, valor)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Código já usado nesta empresa.") from exc
    db.refresh(funcionario)
    return funcionario
