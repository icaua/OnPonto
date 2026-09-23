from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import logging

from sqlalchemy import Connection, Engine, inspect


SCHEMA_VERSION = 9
logger = logging.getLogger(__name__)

COLUNAS_EMPRESA_LEGADAS = (
    "jornada_seg_sex_horas",
    "jornada_sabado_horas",
    "tolerancia_atraso_minutos",
    "tolerancia_extra_minutos",
)
COLUNAS_FUNCIONARIO_LEGADAS = (
    "jornada_especifica_seg_sex_horas",
    "jornada_especifica_sabado_horas",
    "modo_apuracao",
    "horario_entrada_prevista",
    "horario_saida_almoco_prevista",
    "horario_retorno_almoco_prevista",
    "horario_saida_prevista",
)


def _nomes_colunas(conexao: Connection, tabela: str) -> set[str]:
    return {
        linha[1]
        for linha in conexao.exec_driver_sql(f'PRAGMA table_info("{tabela}")').all()
    }


def _valor(
    linha: Mapping[str, Any],
    coluna: str,
    padrao: Any = None,
) -> Any:
    valor = linha.get(coluna, padrao)
    return padrao if valor is None and padrao is not None else valor


def _nome_escala_especifica(nome_funcionario: str) -> str:
    sufixo = " — específica"
    return f"{nome_funcionario[: 120 - len(sufixo)]}{sufixo}"


def _criar_tabela_escalas(conexao: Connection) -> None:
    conexao.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS escalas (
            id INTEGER NOT NULL,
            empresa_id INTEGER NOT NULL,
            nome VARCHAR(120) NOT NULL,
            modo_apuracao VARCHAR(20) NOT NULL,
            jornada_seg_sex_horas FLOAT,
            jornada_sabado_horas FLOAT,
            horario_entrada_prevista TIME,
            horario_saida_almoco_prevista TIME,
            horario_retorno_almoco_prevista TIME,
            horario_saida_prevista TIME,
            regime_sabado VARCHAR(20) NOT NULL,
            regime_domingo VARCHAR(20) NOT NULL,
            tolerancia_atraso_minutos INTEGER NOT NULL,
            tolerancia_extra_minutos INTEGER NOT NULL,
            tolerancia_intervalo_minutos INTEGER NOT NULL,
            ativa BOOLEAN NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(empresa_id) REFERENCES empresas (id)
        )
        """
    )
    conexao.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_escalas_id ON escalas (id)"
    )
    conexao.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_escalas_empresa_id ON escalas (empresa_id)"
    )


def _inserir_escala(
    conexao: Connection,
    *,
    empresa_id: int,
    nome: str,
    modo_apuracao: str,
    jornada_seg_sex_horas: float | None,
    jornada_sabado_horas: float | None,
    horario_entrada_prevista: str | None = None,
    horario_saida_almoco_prevista: str | None = None,
    horario_retorno_almoco_prevista: str | None = None,
    horario_saida_prevista: str | None = None,
    tolerancia_atraso_minutos: int = 0,
    tolerancia_extra_minutos: int = 0,
) -> int:
    regime_sabado = (
        "trabalha"
        if jornada_sabado_horas is not None and float(jornada_sabado_horas) > 0
        else "nao_trabalha"
    )
    cursor = conexao.exec_driver_sql(
        """
        INSERT INTO escalas (
            empresa_id,
            nome,
            modo_apuracao,
            jornada_seg_sex_horas,
            jornada_sabado_horas,
            horario_entrada_prevista,
            horario_saida_almoco_prevista,
            horario_retorno_almoco_prevista,
            horario_saida_prevista,
            regime_sabado,
            regime_domingo,
            tolerancia_atraso_minutos,
            tolerancia_extra_minutos,
            tolerancia_intervalo_minutos,
            ativa,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'nao_trabalha', ?, ?, 0, 1,
                  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            empresa_id,
            nome,
            modo_apuracao,
            jornada_seg_sex_horas,
            jornada_sabado_horas,
            horario_entrada_prevista,
            horario_saida_almoco_prevista,
            horario_retorno_almoco_prevista,
            horario_saida_prevista,
            regime_sabado,
            tolerancia_atraso_minutos,
            tolerancia_extra_minutos,
        ),
    )
    escala_id = cursor.lastrowid
    if escala_id is None:
        raise RuntimeError("Não foi possível identificar a escala criada pela migração.")
    return int(escala_id)


def _migrar_escalas(
    conexao: Connection,
    colunas_empresas: set[str],
    colunas_funcionarios: set[str],
) -> None:
    _criar_tabela_escalas(conexao)

    if "cidade" not in colunas_empresas:
        conexao.exec_driver_sql("ALTER TABLE empresas ADD COLUMN cidade VARCHAR(120)")
        colunas_empresas.add("cidade")
    if "uf" not in colunas_empresas:
        conexao.exec_driver_sql("ALTER TABLE empresas ADD COLUMN uf VARCHAR(2)")
        colunas_empresas.add("uf")
    if "escala_id" not in colunas_funcionarios:
        conexao.exec_driver_sql(
            "ALTER TABLE funcionarios ADD COLUMN escala_id "
            "INTEGER REFERENCES escalas(id)"
        )
        colunas_funcionarios.add("escala_id")
    conexao.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_funcionarios_escala_id "
        "ON funcionarios (escala_id)"
    )

    empresas = conexao.exec_driver_sql(
        "SELECT * FROM empresas ORDER BY id"
    ).mappings().all()
    escalas_padrao: dict[int, int] = {}
    empresas_por_id: dict[int, Mapping[str, Any]] = {}

    for empresa in empresas:
        empresa_id = int(empresa["id"])
        empresas_por_id[empresa_id] = empresa
        jornada_seg_sex = float(_valor(empresa, "jornada_seg_sex_horas", 8.0))
        jornada_sabado = float(_valor(empresa, "jornada_sabado_horas", 4.0))
        tolerancia_atraso = int(_valor(empresa, "tolerancia_atraso_minutos", 5))
        tolerancia_extra = int(_valor(empresa, "tolerancia_extra_minutos", 10))
        escalas_padrao[empresa_id] = _inserir_escala(
            conexao,
            empresa_id=empresa_id,
            nome="Padrão",
            modo_apuracao="carga_horaria",
            jornada_seg_sex_horas=jornada_seg_sex,
            jornada_sabado_horas=jornada_sabado,
            tolerancia_atraso_minutos=tolerancia_atraso,
            tolerancia_extra_minutos=tolerancia_extra,
        )

    funcionarios = conexao.exec_driver_sql(
        "SELECT * FROM funcionarios ORDER BY id"
    ).mappings().all()
    for funcionario in funcionarios:
        empresa_id = int(funcionario["empresa_id"])
        empresa = empresas_por_id.get(empresa_id)
        if empresa is None:
            raise RuntimeError(
                f"Funcionário {funcionario['id']} referencia empresa inexistente."
            )

        modo_apuracao = str(_valor(funcionario, "modo_apuracao", "carga_horaria"))
        jornada_especifica_seg_sex = funcionario.get(
            "jornada_especifica_seg_sex_horas"
        )
        jornada_especifica_sabado = funcionario.get(
            "jornada_especifica_sabado_horas"
        )
        tem_escala_especifica = (
            jornada_especifica_seg_sex is not None
            or jornada_especifica_sabado is not None
            or modo_apuracao == "horario_fixo"
        )

        if tem_escala_especifica:
            jornada_seg_sex = float(
                jornada_especifica_seg_sex
                if jornada_especifica_seg_sex is not None
                else _valor(empresa, "jornada_seg_sex_horas", 8.0)
            )
            jornada_sabado = float(
                jornada_especifica_sabado
                if jornada_especifica_sabado is not None
                else _valor(empresa, "jornada_sabado_horas", 4.0)
            )
            escala_id = _inserir_escala(
                conexao,
                empresa_id=empresa_id,
                nome=_nome_escala_especifica(str(funcionario["nome"])),
                modo_apuracao=modo_apuracao,
                jornada_seg_sex_horas=jornada_seg_sex,
                jornada_sabado_horas=jornada_sabado,
                horario_entrada_prevista=funcionario.get(
                    "horario_entrada_prevista"
                ),
                horario_saida_almoco_prevista=funcionario.get(
                    "horario_saida_almoco_prevista"
                ),
                horario_retorno_almoco_prevista=funcionario.get(
                    "horario_retorno_almoco_prevista"
                ),
                horario_saida_prevista=funcionario.get("horario_saida_prevista"),
                tolerancia_atraso_minutos=int(
                    _valor(empresa, "tolerancia_atraso_minutos", 5)
                ),
                tolerancia_extra_minutos=int(
                    _valor(empresa, "tolerancia_extra_minutos", 10)
                ),
            )
        else:
            escala_id = escalas_padrao[empresa_id]

        conexao.exec_driver_sql(
            "UPDATE funcionarios SET escala_id = ? WHERE id = ?",
            (escala_id, funcionario["id"]),
        )

    sem_escala = conexao.exec_driver_sql(
        """
        SELECT COUNT(*)
        FROM funcionarios AS f
        LEFT JOIN escalas AS e
          ON e.id = f.escala_id AND e.empresa_id = f.empresa_id
        WHERE f.escala_id IS NULL OR e.id IS NULL
        """
    ).scalar_one()
    if sem_escala:
        raise RuntimeError(
            f"Migração interrompida: {sem_escala} funcionário(s) ficaram sem escala."
        )


def _normalizar_status_dia(conexao: Connection, tabelas: set[str]) -> None:
    if "marcacoes_ponto" not in tabelas:
        return
    colunas = _nomes_colunas(conexao, "marcacoes_ponto")
    if {"status_dia", "conferido"}.issubset(colunas):
        conexao.exec_driver_sql(
            """
            UPDATE marcacoes_ponto
            SET status_dia = 'normal', conferido = 0
            WHERE status_dia IN ('pendente', 'pendente_conferencia')
            """
        )


def _tem_unicidade_funcionario_data(conexao: Connection) -> bool:
    for indice in conexao.exec_driver_sql(
        'PRAGMA index_list("marcacoes_ponto")'
    ).mappings():
        if not indice.get("unique"):
            continue
        nome = str(indice["name"]).replace('"', '""')
        colunas = [
            linha["name"]
            for linha in conexao.exec_driver_sql(
                f'PRAGMA index_info("{nome}")'
            ).mappings()
        ]
        if colunas == ["funcionario_id", "data"]:
            return True
    return False


def _garantir_unicidade_funcionario_data(conexao: Connection, tabelas: set[str]) -> None:
    if "marcacoes_ponto" not in tabelas:
        return
    colunas = _nomes_colunas(conexao, "marcacoes_ponto")
    if not {"funcionario_id", "data"}.issubset(colunas):
        return
    if _tem_unicidade_funcionario_data(conexao):
        return

    duplicadas = conexao.exec_driver_sql(
        """
        SELECT funcionario_id, data, COUNT(*) AS total
        FROM marcacoes_ponto
        GROUP BY funcionario_id, data
        HAVING COUNT(*) > 1
        ORDER BY funcionario_id, data
        LIMIT 10
        """
    ).all()
    if duplicadas:
        raise RuntimeError(
            "A migração encontrou marcações duplicadas para funcionário/data; "
            f"nenhum registro foi removido: {duplicadas!r}"
        )
    conexao.exec_driver_sql(
        "CREATE UNIQUE INDEX ux_marcacoes_ponto_funcionario_data "
        "ON marcacoes_ponto (funcionario_id, data)"
    )


def _remover_colunas_legadas(
    conexao: Connection,
    tabela: str,
    colunas: tuple[str, ...],
    sqlite_version: tuple[int, int, int],
) -> None:
    existentes = _nomes_colunas(conexao, tabela)
    para_remover = [coluna for coluna in colunas if coluna in existentes]
    if not para_remover:
        return

    # DROP COLUMN existe desde SQLite 3.35. O runtime distribuído com o projeto
    # usa uma versão mais nova (3.45 no ambiente validado). Falhar e reverter é
    # mais seguro que deixar colunas NOT NULL legadas bloquearem inserts v3.
    if sqlite_version < (3, 35, 0):
        raise RuntimeError(
            "A migração para o schema 3 requer SQLite 3.35 ou mais recente."
        )

    for coluna in para_remover:
        conexao.exec_driver_sql(
            f'ALTER TABLE "{tabela}" DROP COLUMN "{coluna}"'
        )


def _migrar_tolerancia_intervalo(conexao: Connection) -> int:
    colunas = {linha[1]: linha for linha in conexao.exec_driver_sql('PRAGMA table_info("escalas")')}
    if "tolerancia_intervalo_minutos" not in colunas:
        return 0
    convertidas = conexao.exec_driver_sql(
        "SELECT COUNT(*) FROM escalas WHERE tolerancia_intervalo_minutos = 0"
    ).scalar_one()
    if colunas["tolerancia_intervalo_minutos"][3]:
        # Substitui apenas a coluna; IDs, FKs, índices e demais campos permanecem.
        # DDL participa do BEGIN IMMEDIATE externo e reverte inteiro se falhar.
        conexao.exec_driver_sql("ALTER TABLE escalas ADD COLUMN tolerancia_intervalo_v6 INTEGER")
        conexao.exec_driver_sql(
            "UPDATE escalas SET tolerancia_intervalo_v6 = NULLIF(tolerancia_intervalo_minutos, 0)"
        )
        conexao.exec_driver_sql("ALTER TABLE escalas DROP COLUMN tolerancia_intervalo_minutos")
        conexao.exec_driver_sql(
            "ALTER TABLE escalas RENAME COLUMN tolerancia_intervalo_v6 TO tolerancia_intervalo_minutos"
        )
    else:
        conexao.exec_driver_sql(
            "UPDATE escalas SET tolerancia_intervalo_minutos = NULL WHERE tolerancia_intervalo_minutos = 0"
        )
    return int(convertidas)


def _migrar_banco_horas(conexao: Connection, tabelas: set[str]) -> None:
    adicoes = {
        "empresas": {"prazo_compensacao_banco_horas_dias": "INTEGER", "feriado_entra_banco": "BOOLEAN NOT NULL DEFAULT 0"},
        "escalas": {"usa_banco_horas": "BOOLEAN NOT NULL DEFAULT 0"},
        "competencias": {"versao_fechamento": "INTEGER NOT NULL DEFAULT 0"},
    }
    for tabela, campos in adicoes.items():
        if tabela not in tabelas:
            continue
        colunas = _nomes_colunas(conexao, tabela)
        for nome, tipo in campos.items():
            if nome not in colunas:
                conexao.exec_driver_sql(f'ALTER TABLE "{tabela}" ADD COLUMN "{nome}" {tipo}')
    from app.database.models import HistoricoVinculoEscala, LancamentoBancoHoras, CompensacaoBancoHoras
    if {"empresas", "funcionarios", "escalas"}.issubset(tabelas):
        HistoricoVinculoEscala.__table__.create(conexao, checkfirst=True)
        # Só é possível recuperar o vínculo atual, jamais inventar trocas passadas.
        for funcionario in conexao.exec_driver_sql("SELECT * FROM funcionarios WHERE escala_id IS NOT NULL").mappings():
            existe = conexao.exec_driver_sql("SELECT id FROM historico_vinculo_escala WHERE funcionario_id = ? LIMIT 1", (funcionario["id"],)).first()
            if existe:
                continue
            datas = [str(v)[:10] for v in (funcionario.get("created_at"), funcionario.get("data_admissao")) if v]
            if "marcacoes_ponto" in tabelas:
                primeira = conexao.exec_driver_sql("SELECT MIN(data) FROM marcacoes_ponto WHERE funcionario_id = ?", (funcionario["id"],)).scalar_one()
                if primeira:
                    datas.append(str(primeira)[:10])
            from app.banco_horas.politica import hoje_local
            desde = min(datas) if datas else hoje_local().isoformat()
            conexao.exec_driver_sql("""INSERT INTO historico_vinculo_escala
                (funcionario_id, escala_id, vigente_desde, vigente_ate, created_at, updated_at)
                VALUES (?, ?, ?, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                (funcionario["id"], funcionario["escala_id"], desde))
    if {"empresas", "funcionarios", "escalas", "competencias"}.issubset(tabelas):
        LancamentoBancoHoras.__table__.create(conexao, checkfirst=True)
        CompensacaoBancoHoras.__table__.create(conexao, checkfirst=True)


def _aplicar_sqlite(conexao: Connection) -> dict[str, int]:
    tabelas = {
        linha[0]
        for linha in conexao.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).all()
    }

    if "marcacoes_ponto" in tabelas:
        colunas_marcacoes = _nomes_colunas(conexao, "marcacoes_ponto")
        if "historico_json" not in colunas_marcacoes:
            conexao.exec_driver_sql("ALTER TABLE marcacoes_ponto ADD COLUMN historico_json TEXT")
        if "batidas_originais" not in colunas_marcacoes:
            conexao.exec_driver_sql(
                "ALTER TABLE marcacoes_ponto ADD COLUMN batidas_originais TEXT"
            )
        if "arquivo_origem_id" not in colunas_marcacoes:
            conexao.exec_driver_sql(
                "ALTER TABLE marcacoes_ponto ADD COLUMN arquivo_origem_id "
                "INTEGER REFERENCES arquivos_recebidos(id)"
            )
        conexao.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_marcacoes_ponto_arquivo_origem_id "
            "ON marcacoes_ponto (arquivo_origem_id)"
        )

    if "competencias" in tabelas and "apuracao_fechada" not in _nomes_colunas(conexao, "competencias"):
        conexao.exec_driver_sql("ALTER TABLE competencias ADD COLUMN apuracao_fechada TEXT")

    versao_atual = int(
        conexao.exec_driver_sql("PRAGMA user_version").scalar_one()
    )
    if versao_atual < 3 and {"empresas", "funcionarios"}.issubset(tabelas):
        colunas_empresas = _nomes_colunas(conexao, "empresas")
        colunas_funcionarios = _nomes_colunas(conexao, "funcionarios")
        tem_dados_legados = bool(
            set(COLUNAS_EMPRESA_LEGADAS) & colunas_empresas
            or set(COLUNAS_FUNCIONARIO_LEGADAS) & colunas_funcionarios
        )

        _criar_tabela_escalas(conexao)
        if "cidade" not in colunas_empresas:
            conexao.exec_driver_sql(
                "ALTER TABLE empresas ADD COLUMN cidade VARCHAR(120)"
            )
        if "uf" not in colunas_empresas:
            conexao.exec_driver_sql("ALTER TABLE empresas ADD COLUMN uf VARCHAR(2)")
        if "escala_id" not in colunas_funcionarios:
            conexao.exec_driver_sql(
                "ALTER TABLE funcionarios ADD COLUMN escala_id "
                "INTEGER REFERENCES escalas(id)"
            )
        conexao.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_funcionarios_escala_id "
            "ON funcionarios (escala_id)"
        )

        if tem_dados_legados:
            # Recarrega os conjuntos depois das alterações aditivas.
            colunas_empresas = _nomes_colunas(conexao, "empresas")
            colunas_funcionarios = _nomes_colunas(conexao, "funcionarios")
            _migrar_escalas(conexao, colunas_empresas, colunas_funcionarios)

            versao_sqlite_texto = str(
                conexao.exec_driver_sql("SELECT sqlite_version()").scalar_one()
            )
            versao_sqlite = tuple(
                int(parte) for parte in versao_sqlite_texto.split(".")[:3]
            )
            _remover_colunas_legadas(
                conexao,
                "funcionarios",
                COLUNAS_FUNCIONARIO_LEGADAS,
                versao_sqlite,
            )
            _remover_colunas_legadas(
                conexao,
                "empresas",
                COLUNAS_EMPRESA_LEGADAS,
                versao_sqlite,
            )

    _normalizar_status_dia(conexao, tabelas)
    if "funcionarios" in tabelas and "data_admissao" not in _nomes_colunas(conexao, "funcionarios"):
        conexao.exec_driver_sql("ALTER TABLE funcionarios ADD COLUMN data_admissao DATE")
    if "funcionarios" in tabelas and "data_demissao" not in _nomes_colunas(conexao, "funcionarios"):
        conexao.exec_driver_sql("ALTER TABLE funcionarios ADD COLUMN data_demissao DATE")
    if "empresas" in tabelas:
        from app.database.models import EventoCalendario
        EventoCalendario.__table__.create(conexao, checkfirst=True)
    _garantir_unicidade_funcionario_data(conexao, tabelas)
    if "funcionarios" in tabelas:
        from app.database.models import OcorrenciaFuncionario
        OcorrenciaFuncionario.__table__.create(conexao, checkfirst=True)
    convertidas = _migrar_tolerancia_intervalo(conexao) if versao_atual < 6 else 0
    # A migração legada pode ter criado escalas nesta mesma transação.
    tabelas = set(inspect(conexao).get_table_names())
    _migrar_banco_horas(conexao, tabelas)
    if versao_atual < SCHEMA_VERSION:
        conexao.exec_driver_sql(f"PRAGMA user_version = {SCHEMA_VERSION}")
    return {"escalas_intervalo_convertidas": convertidas}


def aplicar_migracoes_compativeis(engine: Engine) -> dict[str, int] | None:
    """Aplica migrações SQLite incrementais, atômicas e idempotentes."""

    if engine.dialect.name != "sqlite":
        # O produto suporta SQLite. Mantém apenas a migração aditiva antiga
        # para engines usadas eventualmente por ferramentas de desenvolvimento.
        inspector = inspect(engine)
        if "marcacoes_ponto" not in inspector.get_table_names():
            return
        colunas = {
            coluna["name"] for coluna in inspector.get_columns("marcacoes_ponto")
        }
        comandos = []
        if "batidas_originais" not in colunas:
            comandos.append(
                "ALTER TABLE marcacoes_ponto ADD COLUMN batidas_originais TEXT"
            )
        if "arquivo_origem_id" not in colunas:
            comandos.append(
                "ALTER TABLE marcacoes_ponto ADD COLUMN arquivo_origem_id INTEGER"
            )
        with engine.begin() as conexao:
            for comando in comandos:
                conexao.exec_driver_sql(comando)
        return

    with engine.connect() as conexao:
        # BEGIN explícito torna DDL transacional mesmo no modo legado do
        # sqlite3 do Python; IMMEDIATE também serializa duas inicializações.
        conexao.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            resultado = _aplicar_sqlite(conexao)
            violacoes = conexao.exec_driver_sql("PRAGMA foreign_key_check").all()
            if violacoes:
                raise RuntimeError(
                    f"Migração gerou violações de chave estrangeira: {violacoes!r}"
                )
            conexao.commit()
            if resultado["escalas_intervalo_convertidas"]:
                logger.warning("Schema 6: %s escala(s) com tolerância de intervalo zero histórico convertidas para NULL (seguir tolerância geral).",
                               resultado["escalas_intervalo_convertidas"])
            return resultado
        except Exception:
            conexao.rollback()
            raise
