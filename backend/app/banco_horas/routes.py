from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.models import Empresa, Funcionario, LancamentoBancoHoras
from app.database.session import get_db
from app.ocorrencias.service import iniciar_escrita
from app.banco_horas import service
from app.banco_horas.schemas import AjusteCreate, EstornoRequest

router = APIRouter(prefix="/banco-horas", tags=["Banco de horas"])


@router.get("/saldo")
def saldo(funcionario_id: int, data_limite: date | None = None, db: Session = Depends(get_db)):
    service.obter_funcionario(db, funcionario_id)
    return {"funcionario_id": funcionario_id, "data_limite": data_limite,
            "saldo_minutos": service.calcular_saldo_banco_horas(db, funcionario_id, data_limite)}


@router.get("/extrato")
def extrato(funcionario_id: int, data_limite: date | None = None, db: Session = Depends(get_db)):
    return service.extrato(db, funcionario_id, data_limite)


@router.get("/resumo")
def resumo(empresa_id: int, db: Session = Depends(get_db)):
    if not db.get(Empresa, empresa_id):
        raise HTTPException(404, "Empresa não encontrada.")
    itens = []
    for f in db.query(Funcionario).filter_by(empresa_id=empresa_id).order_by(Funcionario.nome):
        tem_historico = db.query(LancamentoBancoHoras.id).filter_by(funcionario_id=f.id).first()
        if (f.escala and f.escala.usa_banco_horas) or tem_historico:
            itens.append({"funcionario_id": f.id, "funcionario": f.nome,
                "saldo_minutos": service.calcular_saldo_banco_horas(db, f.id),
                "data_demissao": f.data_demissao,
                "saldo_demissao_minutos": service.calcular_saldo_banco_horas(db, f.id, f.data_demissao) if f.data_demissao else None})
    return itens


@router.get("/alertas")
def alertas(empresa_id: int, dias: int = Query(default=30, ge=0, le=365), db: Session = Depends(get_db)):
    if not db.get(Empresa, empresa_id):
        raise HTTPException(404, "Empresa não encontrada.")
    return service.alertas(db, empresa_id, dias)


@router.post("/ajustes", status_code=201)
def ajustar(payload: AjusteCreate, db: Session = Depends(get_db)):
    try:
        iniciar_escrita(db)
        item = service.ajustar(db, payload)
        db.commit()
        return {"id": item.id, "status": item.status}
    except Exception:
        db.rollback()
        raise


@router.post("/lancamentos/{lancamento_id}/estornar")
def estornar(lancamento_id: int, payload: EstornoRequest, db: Session = Depends(get_db)):
    try:
        iniciar_escrita(db)
        item = service.estornar_ajuste(db, lancamento_id, payload.motivo)
        db.commit()
        return {"id": item.id, "status": item.status}
    except Exception:
        db.rollback()
        raise
