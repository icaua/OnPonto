import json

from app.database.models import FechamentoVersao, ReaberturaFechamento, Funcionario, MarcacaoPonto
from app.funcionarios.historico_escalas import ResolvedorEscalas


def guardar_fechamento(db, competencia, origem="fechamento_local"):
    existente = db.query(FechamentoVersao).filter_by(
        competencia_id=competencia.id, numero=competencia.versao_fechamento).first()
    if existente:
        if existente.snapshot != competencia.apuracao_fechada:
            raise ValueError("Snapshot divergente para versão de fechamento existente.")
        return existente
    if competencia.apuracao_fechada is None:
        registro = FechamentoVersao(competencia_id=competencia.id, numero=competencia.versao_fechamento,
            snapshot=None, regras_json="[]", origem="fechamento_legado_sem_snapshot")
        db.add(registro)
        db.flush()
        return registro
    resolvedor = ResolvedorEscalas(db, competencia.empresa_id)
    funcionarios = {f.id: f for f in db.query(Funcionario).filter_by(empresa_id=competencia.empresa_id)}
    regras = set()
    for funcionario_id, dia in db.query(MarcacaoPonto.funcionario_id, MarcacaoPonto.data).filter_by(competencia_id=competencia.id):
        regra = resolvedor.regra_no_dia(funcionarios[funcionario_id], dia)
        if regra:
            # Cadastro legado direto em ferramentas pode não possuir versão;
            # a ausência é explícita, sem inventar identidade histórica.
            regras.add((regra.id, regra.versao_id))
    registro = FechamentoVersao(competencia_id=competencia.id, numero=competencia.versao_fechamento,
        snapshot=competencia.apuracao_fechada, regras_json=json.dumps(sorted(regras, key=str)), origem=origem)
    db.add(registro)
    db.flush()
    return registro


def registrar_reabertura(db, competencia):
    registro = guardar_fechamento(db, competencia, "snapshot_corrente_legado")
    db.add(ReaberturaFechamento(fechamento_id=registro.id, origem="reabertura_local"))
