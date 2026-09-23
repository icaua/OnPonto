"""Preserva competências anteriores à introdução do snapshot de fechamento."""
import json

from sqlalchemy.orm import Session

from app.apuracao.service import apurar_competencia
from app.database.models import Competencia


def preservar_fechamentos_legados(engine) -> None:
    with Session(engine) as db:
        competencias = db.query(Competencia).filter(
            Competencia.status == "fechada",
            Competencia.apuracao_fechada.is_(None),
        ).all()
        for competencia in competencias:
            resultado = apurar_competencia(db, competencia.id, gerar_calendario=False)
            resultado["preservacao"] = "Dados disponíveis na atualização; regras históricas não recuperáveis."
            competencia.apuracao_fechada = json.dumps(resultado, ensure_ascii=False)
        db.commit()
