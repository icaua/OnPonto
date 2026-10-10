from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.database.recuperacao import criar_conjunto,restaurar_conjunto,sha256
from app.database.migrations import aplicar_migracoes_compativeis
from sqlalchemy import create_engine


class RecuperacaoConjuntoTest(unittest.TestCase):
    def test_backup_restore_schema_antigo_e_evidencias(self):
        with tempfile.TemporaryDirectory(prefix="onponto-conjunto-") as temp:
            root=Path(temp)
            banco=root/"ficticio.db"
            with closing(sqlite3.connect(banco)) as db:
                db.executescript("CREATE TABLE evidencia (id INTEGER PRIMARY KEY,original TEXT); INSERT INTO evidencia VALUES (1,'FICTÍCIO'); PRAGMA user_version=7;")
                db.commit()
            uploads=root/"uploads"
            uploads.mkdir()
            (uploads/"ficticio.txt").write_text("Batidas FICTÍCIAS 08:00 12:00 13:00 17:00",encoding="utf-8")
            original=sha256(banco)
            manifest=criar_conjunto(banco,uploads,root/"backup",offline=True)
            restaurar_conjunto(root/"backup",root/"restaurado")
            self.assertEqual(manifest["banco_sha256"],sha256(root/"restaurado"/"onponto.db"))
            with closing(sqlite3.connect(banco)) as fonte, closing(sqlite3.connect(root/"restaurado"/"onponto.db")) as copia:
                self.assertEqual(list(fonte.iterdump()),list(copia.iterdump()))
                self.assertEqual(fonte.execute("PRAGMA user_version").fetchone(),copia.execute("PRAGMA user_version").fetchone())
            self.assertEqual(sha256(uploads/"ficticio.txt"),manifest["arquivos"]["ficticio.txt"])
            engine=create_engine(f"sqlite:///{root/'restaurado'/'onponto.db'}")
            try:
                aplicar_migracoes_compativeis(engine)
                aplicar_migracoes_compativeis(engine)
                with engine.connect() as conn:
                    self.assertEqual(conn.exec_driver_sql("SELECT original FROM evidencia").scalar_one(),"FICTÍCIO")
                    self.assertEqual(conn.exec_driver_sql("PRAGMA foreign_key_check").all(),[])
                    self.assertEqual(conn.exec_driver_sql("PRAGMA integrity_check").scalar_one(),"ok")
            finally: engine.dispose()
            self.assertEqual(original,sha256(banco))
            with self.assertRaises(FileExistsError): restaurar_conjunto(root/"backup",root/"restaurado")
            (root/"backup"/"uploads"/"ficticio.txt").write_text("adulteração",encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError,"Hash de arquivo"):
                restaurar_conjunto(root/"backup",root/"recusado")
            self.assertFalse((root/"recusado").exists())

    def test_exige_escritores_parados(self):
        with self.assertRaisesRegex(ValueError,"Pare a API"):
            criar_conjunto("ignorado","ignorado","ignorado")
