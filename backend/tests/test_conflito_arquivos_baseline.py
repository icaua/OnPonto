from io import BytesIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.database.session import Base
from app.database.models import Empresa,Escala,Funcionario,Competencia,MarcacaoPonto
from app.importadores import routes
from app.importadores.schemas import ConfirmacaoImportacao


class ArquivosConflitantesBaselineTest(unittest.TestCase):
    def test_dois_arquivos_preservam_primeira_evidencia(self):
        with tempfile.TemporaryDirectory(prefix="onponto-conflito-") as temp:
            engine=create_engine("sqlite://")
            self.addCleanup(engine.dispose)
            Base.metadata.create_all(engine)
            with Session(engine) as db,patch.object(routes,"UPLOADS_DIR",Path(temp)):
                e=Empresa(nome="Empresa FICTÍCIA conflito");db.add(e);db.flush()
                s=Escala(empresa_id=e.id,nome="FICTÍCIA",jornada_seg_sex_horas=8);db.add(s);db.flush()
                f=Funcionario(empresa_id=e.id,nome="Pessoa FICTÍCIA",codigo="F001",escala_id=s.id)
                c=Competencia(empresa_id=e.id,mes=9,ano=2026)
                db.add_all([f,c]);db.commit()
                resultados=[]
                for i,entrada in enumerate(("08:00","09:00")):
                    texto="codigo;nome;data;hora\n"+"\n".join(
                        f"F001;Pessoa FICTÍCIA;2026-09-01;{h}" for h in (entrada,"12:00","13:00","17:00"))
                    previa=routes.analisar_importacao(c.id,e.id,9,2026,
                        UploadFile(filename=f"ficticio-{i}.txt",file=BytesIO(texto.encode())),db)
                    resultados.append(routes.confirmar_importacao(ConfirmacaoImportacao(
                        empresa_id=e.id,competencia_id=c.id,arquivo_id=previa["arquivo"]["id"],
                        registros_ids=[r["id"] for r in previa["preview"]]),db))
                m=db.query(MarcacaoPonto).filter_by(funcionario_id=f.id,data="2026-09-01").one()
                self.assertEqual(str(m.entrada),"08:00:00")
                self.assertIn("08:00",m.batidas_originais)
                self.assertNotIn("09:00",m.batidas_originais)
                self.assertTrue(resultados[1]["conflitos"])
                self.assertEqual(len(list(Path(temp).rglob("*.txt"))),2)
