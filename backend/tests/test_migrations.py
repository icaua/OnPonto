from contextlib import closing
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, event, inspect


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database.migrations import SCHEMA_VERSION, aplicar_migracoes_compativeis


def criar_engine_com_fk(banco: Path):
    engine = create_engine(f"sqlite:///{banco}")

    @event.listens_for(engine, "connect")
    def habilitar_fk(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


def indices_unicos(conexao, tabela: str) -> set[tuple[str, ...]]:
    resultado: set[tuple[str, ...]] = set()
    for indice in conexao.exec_driver_sql(f'PRAGMA index_list("{tabela}")').mappings():
        if not indice["unique"]:
            continue
        nome = str(indice["name"]).replace('"', '""')
        resultado.add(
            tuple(
                linha["name"]
                for linha in conexao.exec_driver_sql(
                    f'PRAGMA index_info("{nome}")'
                ).mappings()
            )
        )
    return resultado


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
                self.assertIn(
                    ("funcionario_id", "data"),
                    indices_unicos(conexao_sqlalchemy, "marcacoes_ponto"),
                )
            engine.dispose()

    def test_migracao_v1_cria_escala_padrao_e_especifica(self) -> None:
        with tempfile.TemporaryDirectory(prefix="onponto-migration-v1-") as pasta:
            banco = Path(pasta) / "legado-v1.db"
            conexao = sqlite3.connect(banco)
            conexao.executescript(
                """
                PRAGMA user_version = 1;
                CREATE TABLE empresas (
                    id INTEGER PRIMARY KEY,
                    nome VARCHAR(180) NOT NULL,
                    cnpj VARCHAR(32),
                    jornada_seg_sex_horas FLOAT NOT NULL,
                    jornada_sabado_horas FLOAT NOT NULL,
                    tolerancia_atraso_minutos INTEGER NOT NULL,
                    tolerancia_extra_minutos INTEGER NOT NULL,
                    ativa BOOLEAN NOT NULL,
                    observacoes TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                );
                CREATE TABLE funcionarios (
                    id INTEGER PRIMARY KEY,
                    empresa_id INTEGER NOT NULL REFERENCES empresas(id),
                    codigo VARCHAR(50),
                    nome VARCHAR(180) NOT NULL,
                    cargo VARCHAR(120),
                    ativo BOOLEAN NOT NULL,
                    jornada_especifica_seg_sex_horas FLOAT,
                    jornada_especifica_sabado_horas FLOAT,
                    observacoes TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    CONSTRAINT uq_funcionario_empresa_codigo
                        UNIQUE (empresa_id, codigo)
                );
                INSERT INTO empresas VALUES (
                    1, 'Empresa V1', NULL, 8, 4, 5, 10, 1, NULL,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                );
                INSERT INTO funcionarios VALUES (
                    10, 1, 'F010', 'Funcionário padrão', NULL, 1,
                    NULL, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                );
                INSERT INTO funcionarios VALUES (
                    11, 1, 'F011', 'Funcionário reduzido', NULL, 1,
                    6, 0, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                );
                """
            )
            conexao.commit()
            conexao.close()

            engine = criar_engine_com_fk(banco)
            aplicar_migracoes_compativeis(engine)
            aplicar_migracoes_compativeis(engine)

            with engine.connect() as conexao_sqlalchemy:
                escalas = conexao_sqlalchemy.exec_driver_sql(
                    """
                    SELECT nome, modo_apuracao, jornada_seg_sex_horas,
                           jornada_sabado_horas, regime_sabado,
                           tolerancia_atraso_minutos,
                           tolerancia_extra_minutos,
                           tolerancia_intervalo_minutos
                    FROM escalas ORDER BY id
                    """
                ).all()
                self.assertEqual(len(escalas), 2)
                self.assertEqual(
                    tuple(escalas[0]),
                    ("Padrão", "carga_horaria", 8.0, 4.0, "trabalha", 5, 10, None),
                )
                self.assertEqual(
                    tuple(escalas[1]),
                    (
                        "Funcionário reduzido — específica",
                        "carga_horaria",
                        6.0,
                        0.0,
                        "nao_trabalha",
                        5,
                        10,
                        None,
                    ),
                )
                vinculados = conexao_sqlalchemy.exec_driver_sql(
                    """
                    SELECT f.id, f.escala_id, e.nome
                    FROM funcionarios AS f
                    JOIN escalas AS e ON e.id = f.escala_id
                    ORDER BY f.id
                    """
                ).all()
                self.assertEqual(len(vinculados), 2)
                self.assertTrue(all(linha.escala_id is not None for linha in vinculados))
                self.assertEqual(vinculados[0].nome, "Padrão")
                self.assertIn("— específica", vinculados[1].nome)
                self.assertEqual(
                    conexao_sqlalchemy.exec_driver_sql(
                        "PRAGMA user_version"
                    ).scalar_one(),
                    SCHEMA_VERSION,
                )
                self.assertEqual(
                    conexao_sqlalchemy.exec_driver_sql(
                        "PRAGMA foreign_keys"
                    ).scalar_one(),
                    1,
                )
                self.assertEqual(
                    conexao_sqlalchemy.exec_driver_sql(
                        "PRAGMA foreign_key_check"
                    ).all(),
                    [],
                )

            colunas_empresa = {
                item["name"] for item in inspect(engine).get_columns("empresas")
            }
            colunas_funcionario = {
                item["name"] for item in inspect(engine).get_columns("funcionarios")
            }
            self.assertTrue({"cidade", "uf"}.issubset(colunas_empresa))
            self.assertIn("escala_id", colunas_funcionario)
            if sqlite3.sqlite_version_info >= (3, 35, 0):
                self.assertTrue(
                    set(
                        (
                            "jornada_seg_sex_horas",
                            "jornada_sabado_horas",
                            "tolerancia_atraso_minutos",
                            "tolerancia_extra_minutos",
                        )
                    ).isdisjoint(colunas_empresa)
                )
                self.assertTrue(
                    {
                        "jornada_especifica_seg_sex_horas",
                        "jornada_especifica_sabado_horas",
                    }.isdisjoint(colunas_funcionario)
                )
            engine.dispose()

    def test_migracao_v2_preserva_horario_fixo_e_normaliza_status(self) -> None:
        with tempfile.TemporaryDirectory(prefix="onponto-migration-v2-") as pasta:
            banco = Path(pasta) / "legado-v2.db"
            conexao = sqlite3.connect(banco)
            conexao.executescript(
                """
                PRAGMA foreign_keys = ON;
                PRAGMA user_version = 2;
                CREATE TABLE empresas (
                    id INTEGER PRIMARY KEY,
                    nome VARCHAR(180) NOT NULL,
                    cnpj VARCHAR(32),
                    jornada_seg_sex_horas FLOAT NOT NULL,
                    jornada_sabado_horas FLOAT NOT NULL,
                    tolerancia_atraso_minutos INTEGER NOT NULL,
                    tolerancia_extra_minutos INTEGER NOT NULL,
                    ativa BOOLEAN NOT NULL,
                    observacoes TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                );
                CREATE TABLE funcionarios (
                    id INTEGER PRIMARY KEY,
                    empresa_id INTEGER NOT NULL REFERENCES empresas(id),
                    codigo VARCHAR(50),
                    nome VARCHAR(180) NOT NULL,
                    cargo VARCHAR(120),
                    ativo BOOLEAN NOT NULL,
                    jornada_especifica_seg_sex_horas FLOAT,
                    jornada_especifica_sabado_horas FLOAT,
                    modo_apuracao VARCHAR(20) NOT NULL,
                    horario_entrada_prevista TIME,
                    horario_saida_almoco_prevista TIME,
                    horario_retorno_almoco_prevista TIME,
                    horario_saida_prevista TIME,
                    observacoes TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    CONSTRAINT uq_funcionario_empresa_codigo
                        UNIQUE (empresa_id, codigo)
                );
                CREATE TABLE arquivos_recebidos (id INTEGER PRIMARY KEY);
                CREATE TABLE marcacoes_ponto (
                    id INTEGER PRIMARY KEY,
                    competencia_id INTEGER NOT NULL,
                    funcionario_id INTEGER NOT NULL REFERENCES funcionarios(id),
                    data DATE NOT NULL,
                    status_dia VARCHAR(30) NOT NULL,
                    origem VARCHAR(30) NOT NULL,
                    conferido BOOLEAN NOT NULL
                );
                INSERT INTO empresas VALUES (
                    1, 'Empresa V2', NULL, 8, 4, 7, 12, 1, NULL,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                );
                INSERT INTO funcionarios VALUES (
                    20, 1, 'F020', 'Funcionário padrão', NULL, 1,
                    NULL, NULL, 'carga_horaria', NULL, NULL, NULL, NULL,
                    NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                );
                INSERT INTO funcionarios VALUES (
                    21, 1, 'F021', 'Funcionário fixo', NULL, 1,
                    NULL, NULL, 'horario_fixo', '08:00:00', '12:00:00',
                    '13:00:00', '17:00:00', NULL,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                );
                INSERT INTO marcacoes_ponto VALUES
                    (1, 100, 20, '2026-07-01', 'pendente', 'manual', 1),
                    (2, 100, 20, '2026-07-02', 'pendente_conferencia', 'manual', 1),
                    (3, 100, 21, '2026-07-03', 'normal', 'manual', 1);
                """
            )
            total_antes = conexao.execute(
                "SELECT COUNT(*) FROM marcacoes_ponto"
            ).fetchone()[0]
            conexao.commit()
            conexao.close()

            engine = criar_engine_com_fk(banco)
            aplicar_migracoes_compativeis(engine)
            aplicar_migracoes_compativeis(engine)

            with engine.connect() as conexao_sqlalchemy:
                self.assertEqual(
                    conexao_sqlalchemy.exec_driver_sql(
                        "SELECT COUNT(*) FROM escalas"
                    ).scalar_one(),
                    2,
                )
                self.assertEqual(
                    conexao_sqlalchemy.exec_driver_sql(
                        "SELECT COUNT(*) FROM funcionarios WHERE escala_id IS NULL"
                    ).scalar_one(),
                    0,
                )
                escala_fixa = conexao_sqlalchemy.exec_driver_sql(
                    """
                    SELECT e.nome, e.modo_apuracao,
                           e.horario_entrada_prevista,
                           e.horario_saida_almoco_prevista,
                           e.horario_retorno_almoco_prevista,
                           e.horario_saida_prevista,
                           e.jornada_seg_sex_horas,
                           e.jornada_sabado_horas,
                           e.regime_sabado,
                           e.tolerancia_atraso_minutos,
                           e.tolerancia_extra_minutos
                    FROM escalas AS e
                    JOIN funcionarios AS f ON f.escala_id = e.id
                    WHERE f.id = 21
                    """
                ).one()
                self.assertEqual(
                    tuple(escala_fixa),
                    (
                        "Funcionário fixo — específica",
                        "horario_fixo",
                        "08:00:00",
                        "12:00:00",
                        "13:00:00",
                        "17:00:00",
                        8.0,
                        4.0,
                        "trabalha",
                        7,
                        12,
                    ),
                )
                total_depois = conexao_sqlalchemy.exec_driver_sql(
                    "SELECT COUNT(*) FROM marcacoes_ponto"
                ).scalar_one()
                self.assertEqual(total_depois, total_antes)
                statuses = conexao_sqlalchemy.exec_driver_sql(
                    "SELECT id, status_dia, conferido FROM marcacoes_ponto ORDER BY id"
                ).all()
                self.assertEqual(
                    [tuple(linha) for linha in statuses],
                    [
                        (1, "normal", 0),
                        (2, "normal", 0),
                        (3, "normal", 1),
                    ],
                )
                self.assertEqual(
                    conexao_sqlalchemy.exec_driver_sql(
                        "PRAGMA user_version"
                    ).scalar_one(),
                    SCHEMA_VERSION,
                )
                self.assertEqual(
                    conexao_sqlalchemy.exec_driver_sql(
                        "PRAGMA foreign_key_check"
                    ).all(),
                    [],
                )
                self.assertEqual(
                    conexao_sqlalchemy.exec_driver_sql(
                        "PRAGMA integrity_check"
                    ).scalar_one(),
                    "ok",
                )
                self.assertIn(
                    ("funcionario_id", "data"),
                    indices_unicos(conexao_sqlalchemy, "marcacoes_ponto"),
                )

            colunas_funcionario = {
                item["name"] for item in inspect(engine).get_columns("funcionarios")
            }
            if sqlite3.sqlite_version_info >= (3, 35, 0):
                self.assertTrue(
                    {
                        "jornada_especifica_seg_sex_horas",
                        "jornada_especifica_sabado_horas",
                        "modo_apuracao",
                        "horario_entrada_prevista",
                        "horario_saida_almoco_prevista",
                        "horario_retorno_almoco_prevista",
                        "horario_saida_prevista",
                    }.isdisjoint(colunas_funcionario)
                )
            engine.dispose()

    def test_migracao_interrompe_sem_apagar_duplicidade_funcionario_data(self) -> None:
        with tempfile.TemporaryDirectory(prefix="onponto-migration-duplicate-") as pasta:
            banco = Path(pasta) / "duplicado.db"
            with closing(sqlite3.connect(banco)) as conexao:
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
                    INSERT INTO marcacoes_ponto VALUES
                        (1, 10, 20, '2026-07-01', 'manual'),
                        (2, 11, 20, '2026-07-01', 'manual');
                    """
                )

            engine = create_engine(f"sqlite:///{banco}")
            with self.assertRaisesRegex(RuntimeError, "nenhum registro foi removido"):
                aplicar_migracoes_compativeis(engine)
            engine.dispose()

            with closing(sqlite3.connect(banco)) as conexao:
                self.assertEqual(
                    conexao.execute("SELECT COUNT(*) FROM marcacoes_ponto").fetchone()[0],
                    2,
                )
                self.assertEqual(conexao.execute("PRAGMA user_version").fetchone()[0], 0)
                self.assertEqual(
                    [
                        linha[1]
                        for linha in conexao.execute(
                            "PRAGMA table_info(marcacoes_ponto)"
                        )
                    ],
                    ["id", "competencia_id", "funcionario_id", "data", "origem"],
                )


if __name__ == "__main__":
    unittest.main()
