from fastapi import HTTPException
from app.database.models import DependenciaFechamento, FechamentoVersao, Competencia, MarcacaoPonto


def exigir_referencias_editaveis(db, funcionario_id=None, inicio=None, fim=None, marcacao_id=None, empresa_id=None):
    query = db.query(DependenciaFechamento.id).join(FechamentoVersao,
        FechamentoVersao.id==DependenciaFechamento.fechamento_id).join(Competencia,
        Competencia.id==FechamentoVersao.competencia_id).join(MarcacaoPonto,
        MarcacaoPonto.id==DependenciaFechamento.marcacao_id).filter(
        Competencia.status=="fechada",Competencia.versao_fechamento==FechamentoVersao.numero)
    if funcionario_id is not None: query=query.filter(MarcacaoPonto.funcionario_id==funcionario_id)
    if marcacao_id is not None: query=query.filter(MarcacaoPonto.id==marcacao_id)
    if inicio is not None: query=query.filter(MarcacaoPonto.data>=inicio)
    if fim is not None: query=query.filter(MarcacaoPonto.data<=fim)
    if empresa_id is not None: query=query.filter(Competencia.empresa_id==empresa_id)
    if query.first():
        raise HTTPException(409, "O período participa do DSR de uma competência fechada. Reabra esse fechamento antes de revisar sua referência.")
