import asyncio
from datetime import date, datetime, timedelta, time
from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from openpyxl import load_workbook
from app.database.session import Base
from app.database.models import Competencia, LancamentoBancoHoras, CompensacaoBancoHoras
from app.apuracao.service import apurar_competencia
from app.competencias.routes import fechar_competencia, reabrir_competencia
from app.competencias.schemas import FechamentoCompetenciaRequest
from app.relatorios.routes import exportar_excel
from synthetic_scenarios import criar_cenario,normalizar

GOLDEN=Path(__file__).parent/"fixtures"/"golden_baseline.json"


def json_value(value):
    if isinstance(value,(date,datetime,time)): return value.isoformat()
    if isinstance(value,timedelta): return int(value.total_seconds()/60)
    raise TypeError(type(value).__name__)


async def conteudo(response):
    return b"".join([chunk async for chunk in response.body_iterator])


def capturar():
    engine=create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            ids=criar_cenario(db)
            aberto=apurar_competencia(db,ids["aberta"])
            fechar_competencia(ids["fechavel"],FechamentoCompetenciaRequest(),db)
            snapshot=json.loads(db.get(Competencia,ids["fechavel"]).apuracao_fechada)
            workbook=load_workbook(BytesIO(asyncio.run(conteudo(exportar_excel(ids["fechavel"],db)))),data_only=True)
            excel={ws.title:list(ws.values) for ws in workbook}
            workbook.close()
            reabrir_competencia(ids["fechavel"],db)
            fechar_competencia(ids["fechavel"],FechamentoCompetenciaRequest(),db)
            ledger=[{col.name:getattr(l,col.name) for col in LancamentoBancoHoras.__table__.columns}
                for l in db.query(LancamentoBancoHoras).order_by(LancamentoBancoHoras.id)]
            compensacoes=[{col.name:getattr(l,col.name) for col in CompensacaoBancoHoras.__table__.columns}
                for l in db.query(CompensacaoBancoHoras).order_by(CompensacaoBancoHoras.id)]
            value=normalizar({"aberto":aberto,"snapshot":snapshot,"ledger":ledger,
                "compensacoes":compensacoes,"excel":excel})
            return json.loads(json.dumps(value,default=json_value,ensure_ascii=False))
    finally:
        engine.dispose()


class GoldenBaselineTest(unittest.TestCase):
    def test_resultados_legados_e_exportacao(self):
        self.maxDiff=4000
        self.assertEqual(capturar(),json.loads(GOLDEN.read_text(encoding="utf-8")))


if __name__=="__main__":
    if sys.argv[1:]==["--gravar-baseline"]:
        GOLDEN.write_text(json.dumps(capturar(),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(GOLDEN)
    else: unittest.main()
