from sqlalchemy import Engine, inspect


SCHEMA_VERSION = 1


def aplicar_migracoes_compativeis(engine: Engine) -> None:
    """Aplica apenas alterações aditivas compatíveis com o SQLite existente."""

    inspector = inspect(engine)
    if "marcacoes_ponto" not in inspector.get_table_names():
        return

    colunas = {coluna["name"] for coluna in inspector.get_columns("marcacoes_ponto")}
    comandos: list[str] = []
    if "batidas_originais" not in colunas:
        comandos.append("ALTER TABLE marcacoes_ponto ADD COLUMN batidas_originais TEXT")
    if "arquivo_origem_id" not in colunas:
        comandos.append(
            "ALTER TABLE marcacoes_ponto ADD COLUMN arquivo_origem_id "
            "INTEGER REFERENCES arquivos_recebidos(id)"
        )

    with engine.begin() as conexao:
        for comando in comandos:
            conexao.exec_driver_sql(comando)
        if engine.dialect.name == "sqlite":
            conexao.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_marcacoes_ponto_arquivo_origem_id "
                "ON marcacoes_ponto (arquivo_origem_id)"
            )
            versao_atual = conexao.exec_driver_sql("PRAGMA user_version").scalar_one()
            if versao_atual < SCHEMA_VERSION:
                conexao.exec_driver_sql(f"PRAGMA user_version = {SCHEMA_VERSION}")
