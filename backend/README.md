# Backend On Ponto

API FastAPI do On Ponto `1.0.0-rc.1`. O fluxo homologado do MVP cobre cadastros, importação de TXT estruturado, conferência, apuração, exportação e fechamento de competências.

Para a instalação normal, prefira os scripts da raiz do projeto descritos no [README principal](../README.md). Eles criam e usam uma virtualenv `.venv` local, sem instalar pacotes globalmente.

## Execução manual

A partir da raiz do projeto:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

No Windows, use `.venv\Scripts\python.exe` no lugar de `.venv/bin/python`.

A API fica disponível em:

- http://127.0.0.1:8000
- http://127.0.0.1:8000/docs

Por padrão, o SQLite fica em `backend/onponto.db` e os arquivos enviados em `backend/uploads/`, sempre resolvidos a partir do projeto, não do diretório atual do terminal. Para testes isolados, podem ser definidos:

- `ONPONTO_DATABASE_URL`, com uma URL SQLAlchemy;
- `ONPONTO_UPLOADS_DIR`, com um caminho absoluto para os uploads.

Na inicialização, migrações SQLite incrementais e idempotentes acrescentam os campos necessários ao MVP. Elas não apagam nem recriam o banco existente.

## Contrato principal

- `GET/POST/PATCH /empresas`
- `GET/POST/PATCH /funcionarios`
- `GET/POST/PATCH /competencias`
- `POST /competencias/{id}/fechar`
- `POST /competencias/{id}/reabrir`
- `GET/POST /arquivos`
- `GET /arquivos/{arquivo_id}/download`
- `POST /importadores/txt-log-relogio/analisar`
- `POST /importadores/txt-log-relogio/confirmar`
- `GET/POST/PATCH /marcacoes`
- `GET /apuracao?competencia_id={id}`
- `GET /relatorios/excel?competencia_id={id}`
- `GET /relatorios/impressao?competencia_id={id}`

O parser TXT aceita UTF-16, UTF-8 com BOM e UTF-8, exige as colunas `EnNo`, `Name` e `DateTime` e preserva todas as batidas originais com segundos. A confirmação persiste somente registros válidos e selecionados; funcionário desconhecido, data fora da competência e reimportação permanecem conflitos explícitos.

O status da competência é controlado pelas ações de fechamento e reabertura. Uma competência fechada continua disponível para consulta, download e exportação, mas rejeita importações, uploads e edições até ser reaberta.

## Testes

A partir da raiz do projeto:

```bash
.venv/bin/python -m unittest discover -s backend/tests -v
.venv/bin/python -m compileall -q backend/app backend/tests seed_demo.py
```

No Windows, substitua `.venv/bin/python` por `.venv\Scripts\python.exe`.

O escopo congelado e as evidências de aceite estão no [checklist do MVP](../CHECKLIST-CONGELAMENTO-MVP.md).
