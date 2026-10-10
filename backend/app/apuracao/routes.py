from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.apuracao.service import apurar_competencia
from app.database.session import get_db


router = APIRouter(prefix="/apuracao", tags=["Apuração"])


@router.get("")
def obter_apuracao(
    competencia_id: int = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    resultado = apurar_competencia(db, competencia_id)
    if not resultado:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")
    return resultado


@router.get("/triagem")
def obter_triagem(competencia_id: int = Query(...),db: Session = Depends(get_db)):
    from app.apuracao.triagem import consultar_triagem
    resultado=consultar_triagem(db,competencia_id)
    if resultado is None: raise HTTPException(404,"Competência não encontrada.")
    return resultado


@router.get("/resumo")
def obter_resumo(competencia_id: int = Query(...),db: Session = Depends(get_db)):
    resultado=obter_apuracao(competencia_id,db)
    return {k:v for k,v in resultado.items() if k not in ("marcacoes","pendencias")}


@router.get("/dias")
def obter_dias(competencia_id: int = Query(...),funcionario_id: int = Query(...),db: Session = Depends(get_db)):
    from sqlalchemy import text
    from sqlalchemy.orm import joinedload
    from app.database.models import MarcacaoPonto
    from app.marcacoes.schemas import MarcacaoRead
    if db.get_bind().dialect.name == "sqlite":
        conexao=db.connection()
        if not conexao.connection.driver_connection.in_transaction: db.execute(text("BEGIN"))
    from app.database.models import Competencia, Funcionario
    from app.apuracao.contexto import ContextoApuracao
    c=db.get(Competencia,competencia_id)
    f=db.get(Funcionario,funcionario_id)
    if c is None or f is None or f.empresa_id!=c.empresa_id: raise HTTPException(404,"Competência/funcionário não encontrado.")
    if c.status=="fechada":
        resultado=obter_apuracao(competencia_id,db)
        registros=db.query(MarcacaoPonto).options(joinedload(MarcacaoPonto.arquivo_origem)).filter_by(
            competencia_id=c.id,funcionario_id=funcionario_id).order_by(MarcacaoPonto.data).all()
        return {"competencia":resultado["competencia"],"marcacoes":[d for d in resultado["marcacoes"] if d["funcionario_id"]==funcionario_id],
            "registros":[MarcacaoRead.model_validate(m).model_dump(mode="json") for m in registros]}
    contexto=ContextoApuracao(db,c,funcionario_id)
    return {"competencia":{"id":c.id,"status":c.status},"marcacoes":contexto.detalhes(funcionario_id),
        "registros":[MarcacaoRead.model_validate(m).model_dump(mode="json") for m in contexto.marcacoes]}


@router.get("/{competencia_id}")
def obter_apuracao_por_rota(competencia_id: int, db: Session = Depends(get_db)) -> dict:
    resultado = apurar_competencia(db, competencia_id)
    if not resultado:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")
    return resultado
