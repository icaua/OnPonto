from contextlib import closing
from datetime import datetime, timedelta
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database.backup import realizar_backups_automaticos, pasta_backups
from app.database.migrations import SCHEMA_VERSION
from app.database.session import BACKEND_DIR
from app import main


class BackupAutomaticoTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pasta = Path(self.temp.name)
        self.banco = self.pasta / "origem.db"
        self.engine = create_engine(f"sqlite:///{self.banco}")
        self.addCleanup(self.engine.dispose)
        ambiente = patch.dict(os.environ)
        ambiente.start()
        self.addCleanup(ambiente.stop)
        os.environ.pop("ONPONTO_BACKUP_DIR", None)

    def criar_banco(self, versao=SCHEMA_VERSION):
        with closing(sqlite3.connect(self.banco)) as db:
            db.executescript(f"CREATE TABLE prova (valor TEXT); INSERT INTO prova VALUES ('preservado'); PRAGMA user_version={versao};")

    def subir(self):
        with patch.object(main, "engine", self.engine):
            main.criar_tabelas()

    def test_pre_migracao_preserva_versao_dados_e_integridade(self):
        self.criar_banco(12)
        with self.assertLogs("app.database.backup", level="INFO") as logs:
            self.subir()
        copia, = (self.pasta / "backups").glob(f"onponto-v12-antes-da-v{SCHEMA_VERSION}-*.db")
        caminhos_logados = [Path(r.args[0]) for r in logs.records
                           if r.msg == "Backup automático criado: %s"]
        self.assertTrue(any(copia.samefile(p) for p in caminhos_logados))
        with closing(sqlite3.connect(copia)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 12)
            self.assertEqual(db.execute("SELECT * FROM prova").fetchall(), [("preservado",)])
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
            self.assertNotIn("empresas", [r[0] for r in db.execute("SELECT name FROM sqlite_master")])
        with closing(sqlite3.connect(self.banco)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)

    def test_diario_unico_por_dia(self):
        self.criar_banco()
        self.subir()
        copia, = (self.pasta / "backups").glob("*.db")
        conteudo = copia.read_bytes()
        self.subir()
        self.assertEqual(list((self.pasta / "backups").glob("*.db")), [copia])
        self.assertEqual(copia.read_bytes(), conteudo)
        self.assertEqual(copia.name, f"onponto-diario-{datetime.now():%Y%m%d}.db")

    def test_retencao_10_pre_migracao_e_7_diarios(self):
        self.criar_banco(12)
        pasta = self.pasta / "backups"
        pasta.mkdir()
        antigos = []
        for i in range(15):
            data = datetime(2020, 1, 1) + timedelta(days=i)
            for nome in (f"onponto-v{15-i}-antes-da-v20-{data:%Y%m%d-%H%M%S}.db", f"onponto-diario-{data:%Y%m%d}.db"):
                (pasta / nome).write_bytes(b"antigo")
                if i == 0:
                    antigos.append(pasta / nome)
        outro = pasta / "manual.db"
        outro.write_bytes(b"manual")
        realizar_backups_automaticos(self.engine)
        self.assertEqual(len(list(pasta.glob("onponto-v*.db"))), 10)
        self.assertEqual(len(list(pasta.glob("onponto-diario-*.db"))), 7)
        self.assertTrue(all(not p.exists() for p in antigos))
        self.assertEqual(outro.read_bytes(), b"manual")

    def test_falha_pre_migracao_impede_qualquer_escrita_startup(self):
        self.criar_banco(12)
        antes = self.banco.read_bytes()
        (self.pasta / "backups").write_text("não é pasta")
        with self.assertRaisesRegex(RuntimeError, "backup pré-migração.*Inicialização cancelada"):
            self.subir()
        self.assertEqual(self.banco.read_bytes(), antes)

    def test_falha_diario_apenas_avisa_e_permite_startup(self):
        self.criar_banco()
        (self.pasta / "backups").write_text("não é pasta")
        with self.assertLogs("app.database.backup", level="WARNING") as logs:
            self.subir()
        self.assertTrue(any("backup diário" in linha for linha in logs.output))

    def test_banco_memoria_ou_inexistente_nao_cria_copias(self):
        for url in ("sqlite://", "sqlite:///:memory:", "sqlite:///file:teste?mode=memory&uri=true"):
            engine = create_engine(url)
            try:
                realizar_backups_automaticos(engine)
            finally:
                engine.dispose()
        realizar_backups_automaticos(self.engine)
        self.assertEqual(list(self.pasta.iterdir()), [])

    def test_pasta_configurada_e_respeitada(self):
        self.criar_banco()
        destino = self.pasta / "escolhida"
        with patch.dict(os.environ, ONPONTO_BACKUP_DIR=str(destino)):
            realizar_backups_automaticos(self.engine)
        self.assertEqual(len(list(destino.glob("*.db"))), 1)
        self.assertFalse((self.pasta / "backups").exists())

    def test_pasta_padrao_so_para_banco_real(self):
        self.assertEqual(pasta_backups((BACKEND_DIR / "onponto.db").resolve()), BACKEND_DIR.parent / "backups" / "automaticos")
        self.assertEqual(pasta_backups(self.banco), self.pasta / "backups")

    def test_copia_inclui_transacao_confirmada_em_wal(self):
        self.criar_banco(12)
        with closing(sqlite3.connect(self.banco)) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("INSERT INTO prova VALUES ('no WAL')")
            db.commit()
            realizar_backups_automaticos(self.engine)
            copia, = (self.pasta / "backups").glob("onponto-v*.db")
            with closing(sqlite3.connect(copia)) as destino:
                self.assertEqual(destino.execute("SELECT * FROM prova").fetchall(), [("preservado",), ("no WAL",)])

    def test_falha_integridade_nao_publica_copia_nem_migra(self):
        self.criar_banco(12)
        antes = self.banco.read_bytes()
        with patch("app.database.backup.criar_copia", side_effect=RuntimeError("integridade inválida")):
            with self.assertRaisesRegex(RuntimeError, "integridade inválida"):
                self.subir()
        self.assertEqual(self.banco.read_bytes(), antes)


if __name__ == "__main__":
    unittest.main()
