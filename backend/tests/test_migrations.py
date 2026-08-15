import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database.migrations import SCHEMA_VERSION, aplicar_migracoes_compativeis


class MigracaoCompativelTest(unittest.TestCase):
    def test_migracao_eh_idempotente_e_preserva_dados(self) -> None:
        with tempfile.TemporaryDirectory(prefix="onponto-migration-") as pasta:
            banco = Path(pasta) / "legado.db"
            conexao = sqlite3.connect(banco)
            conexao.executescript(
                """
                CREATE TABLE arquivos_recebidos (id INTEGER PRIMARY KEY);
                CREATE TABLE marcacoes_ponto (
                    id INTEGER PRIMARY KEY,
                    competencia_id INTEGER NOT NULL,
                    funcionario_id INTEGER NOT NULL,
                    data DATE NOT NULL,
                    origem VARCHAR(30) NOT NULL
                );
                INSERT INTO marcacoes_ponto
                    (id, competencia_id, funcionario_id, data, origem)
                VALUES (1, 10, 20, '2026-07-01', 'manual');
                """
            )
            conexao.commit()
            conexao.close()

            engine = create_engine(f"sqlite:///{banco}")
            aplicar_migracoes_compativeis(engine)
            aplicar_migracoes_compativeis(engine)

            colunas = {item["name"] for item in inspect(engine).get_columns("marcacoes_ponto")}
            self.assertIn("batidas_originais", colunas)
            self.assertIn("arquivo_origem_id", colunas)
            with engine.connect() as conexao_sqlalchemy:
                linha = conexao_sqlalchemy.exec_driver_sql(
                    "SELECT id, origem, batidas_originais, arquivo_origem_id FROM marcacoes_ponto"
                ).one()
                self.assertEqual(tuple(linha), (1, "manual", None, None))
                self.assertEqual(
                    conexao_sqlalchemy.exec_driver_sql("PRAGMA user_version").scalar_one(),
                    SCHEMA_VERSION,
                )
                self.assertEqual(
                    conexao_sqlalchemy.exec_driver_sql("PRAGMA integrity_check").scalar_one(), "ok"
                )
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
