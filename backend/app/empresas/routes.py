from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.models import Empresa, Escala
from app.database.session import get_db
from app.empresas.schemas import EmpresaCreate, EmpresaRead, EmpresaUpdate
from app.ocorrencias.service import iniciar_escrita


router = APIRouter(prefix="/empresas", tags=["Empresas"])


@router.get("", response_model=list[EmpresaRead])
def listar_empresas(db: Session = Depends(get_db)) -> list[Empresa]:
    return db.query(Empresa).order_by(Empresa.nome.asc()).all()


@router.post("", response_model=EmpresaRead, status_code=status.HTTP_201_CREATED)
def criar_empresa(payload: EmpresaCreate, db: Session = Depends(get_db)) -> Empresa:
    empresa = Empresa(**payload.model_dump())
    db.add(empresa)
    db.commit()
    db.refresh(empresa)
    return empresa


@router.get("/{empresa_id}", response_model=EmpresaRead)
def obter_empresa(empresa_id: int, db: Session = Depends(get_db)) -> Empresa:
    empresa = db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    return empresa


@router.patch("/{empresa_id}", response_model=EmpresaRead)
def atualizar_empresa(empresa_id: int, payload: EmpresaUpdate, db: Session = Depends(get_db)) -> Empresa:
    iniciar_escrita(db)
    empresa = db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")

    dados = payload.model_dump(exclude_unset=True)
    if "prazo_compensacao_banco_horas_dias" in dados and dados["prazo_compensacao_banco_horas_dias"] is None:
        if db.query(Escala.id).filter_by(empresa_id=empresa.id, usa_banco_horas=True).first():
            raise HTTPException(409, "Não é possível remover o prazo enquanto houver escala com banco de horas habilitado.")
    for campo, valor in dados.items():
        setattr(empresa, campo, valor)

    db.commit()
    db.refresh(empresa)
    return empresa
