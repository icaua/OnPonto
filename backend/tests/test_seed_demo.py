from __future__ import annotations

from contextlib import closing

import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_PATH = PROJECT_ROOT / "seed_demo.py"


class SeedDemoTest(unittest.TestCase):
    def executar_seed(
        self,
        banco: Path,
        cwd_externo: Path,
    ) -> subprocess.CompletedProcess[str]:
        uploads = banco.parent / "uploads"
        uploads.mkdir(exist_ok=True)
        ambiente = os.environ.copy()
        ambiente["ONPONTO_DATABASE_URL"] = f"sqlite:///{banco}"
        ambiente["ONPONTO_UPLOADS_DIR"] = str(uploads)
        ambiente["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, str(SEED_PATH)],
            cwd=cwd_externo,
            env=ambiente,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

    def test_primeira_e_segunda_execucao_sao_idempotentes_e_preservam_fechamento(self) -> None:
        with tempfile.TemporaryDirectory(prefix="onponto-seed-") as pasta:
            raiz = Path(pasta)
            banco = raiz / "seed.test.db"
            cwd_externo = raiz / "execucao fora do projeto"
            cwd_externo.mkdir()

            primeira = self.executar_seed(banco, cwd_externo)
            self.assertEqual(primeira.returncode, 0, primeira.stderr)
            self.assertIn("Seed de demonstração concluído.", primeira.stdout)
            self.assertIn("Resumo: 5 criado(s), 0 reutilizado(s).", primeira.stdout)
            self.assertIn("O código X999 permanece sem cadastro", primeira.stdout)

            with closing(sqlite3.connect(banco)) as conexao:
                empresa = conexao.execute(
                    "SELECT id, nome FROM empresas WHERE nome = ?",
                    ("Empresa Demonstração",),
                ).fetchone()
                self.assertIsNotNone(empresa)
                empresa_id = empresa[0]

                funcionarios = conexao.execute(
                    "SELECT id, codigo, nome, escala_id FROM funcionarios "
                    "WHERE empresa_id = ? ORDER BY codigo",
                    (empresa_id,),
                ).fetchall()
                self.assertEqual(
                    [(item[1], item[2]) for item in funcionarios],
                    [("F001", "Alice Teste"), ("F002", "Bruno Teste")],
                )
                self.assertTrue(all(item[3] is not None for item in funcionarios))
                self.assertNotIn(
                    "X999",
                    {
                        item[0]
                        for item in conexao.execute(
                            "SELECT codigo FROM funcionarios WHERE empresa_id = ?",
                            (empresa_id,),
                        ).fetchall()
                    },
                )

                competencia = conexao.execute(
                    "SELECT id, status, data_fechamento FROM competencias "
                    "WHERE empresa_id = ? AND mes = 7 AND ano = 2026",
                    (empresa_id,),
                ).fetchone()
                self.assertIsNotNone(competencia)
                competencia_id = competencia[0]
                self.assertEqual(competencia[1:], ("aberta", None))

                conexao.execute(
                    "UPDATE competencias SET status = ?, data_fechamento = ? WHERE id = ?",
                    ("fechada", "2026-07-31", competencia_id),
                )
                conexao.commit()

            segunda = self.executar_seed(banco, cwd_externo)
            self.assertEqual(segunda.returncode, 0, segunda.stderr)
            self.assertIn("Resumo: 0 criado(s), 5 reutilizado(s).", segunda.stdout)
            self.assertIn("situação preservada: fechada", segunda.stdout)

            with closing(sqlite3.connect(banco)) as conexao:
                self.assertEqual(
                    conexao.execute(
                        "SELECT COUNT(*) FROM empresas WHERE nome = ?",
                        ("Empresa Demonstração",),
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    conexao.execute(
                        "SELECT COUNT(*) FROM funcionarios WHERE empresa_id = ?",
                        (empresa_id,),
                    ).fetchone()[0],
                    2,
                )
                self.assertEqual(
                    conexao.execute(
                        "SELECT id, status, data_fechamento FROM competencias "
                        "WHERE empresa_id = ? AND mes = 7 AND ano = 2026",
                        (empresa_id,),
                    ).fetchone(),
                    (competencia_id, "fechada", "2026-07-31"),
                )

    def test_conflito_de_integridade_reverte_toda_a_execucao(self) -> None:
        with tempfile.TemporaryDirectory(prefix="onponto-seed-conflito-") as pasta:
            raiz = Path(pasta)
            banco = raiz / "seed-conflito.test.db"
            cwd_externo = raiz / "outro cwd"
            cwd_externo.mkdir()

            preparacao = self.executar_seed(banco, cwd_externo)
            self.assertEqual(preparacao.returncode, 0, preparacao.stderr)

            with closing(sqlite3.connect(banco)) as conexao:
                conexao.execute("DELETE FROM competencias")
                conexao.execute("DELETE FROM funcionarios")
                conexao.execute("DELETE FROM escalas")
                conexao.execute("DELETE FROM empresas")
                conexao.execute(
                    "INSERT INTO empresas ("
                    "nome, cnpj, cidade, uf, ativa, observacoes, created_at, updated_at"
                    ") VALUES (?, NULL, NULL, NULL, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                    ("Empresa Sentinela", "Cadastro preexistente que deve permanecer intacto."),
                )
                sentinela_id = conexao.execute(
                    "SELECT id FROM empresas WHERE nome = ?",
                    ("Empresa Sentinela",),
                ).fetchone()[0]
                conexao.execute(
                    "CREATE TRIGGER conflito_seed_f002 "
                    "BEFORE INSERT ON funcionarios "
                    "WHEN NEW.codigo = 'F002' "
                    "BEGIN SELECT RAISE(ABORT, 'conflito proposital do teste'); END"
                )
                conexao.commit()

            conflito = self.executar_seed(banco, cwd_externo)
            self.assertEqual(conflito.returncode, 2)
            self.assertIn("conflito de integridade", conflito.stderr)
            self.assertIn("nada foi criado", conflito.stderr)

            with closing(sqlite3.connect(banco)) as conexao:
                self.assertEqual(
                    conexao.execute(
                        "SELECT id, nome, observacoes FROM empresas ORDER BY id"
                    ).fetchall(),
                    [
                        (
                            sentinela_id,
                            "Empresa Sentinela",
                            "Cadastro preexistente que deve permanecer intacto.",
                        )
                    ],
                )
                self.assertEqual(
                    conexao.execute("SELECT COUNT(*) FROM funcionarios").fetchone()[0],
                    0,
                )
                self.assertEqual(
                    conexao.execute("SELECT COUNT(*) FROM competencias").fetchone()[0],
                    0,
                )


if __name__ == "__main__":
    unittest.main()
