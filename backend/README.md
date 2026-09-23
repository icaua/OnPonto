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

Na inicialização, migrações SQLite incrementais e idempotentes evoluem o schema e preservam os cadastros existentes.

## Contrato principal

- `GET/POST/PATCH /empresas`
- `GET/POST /escalas`, `GET/PUT/DELETE /escalas/{id}`
- `GET/POST/PATCH /funcionarios`
- `GET/POST/PATCH /competencias`
- `POST /competencias/{id}/fechar`
- `POST /competencias/{id}/reabrir`
- `GET/POST /arquivos`
- `GET /arquivos/{arquivo_id}/download`
- `POST /importadores/analisar`
- `POST /importadores/confirmar`
- `GET/POST/PATCH /marcacoes`
- `GET /apuracao?competencia_id={id}`
- `GET /relatorios/excel?competencia_id={id}`
- `GET /relatorios/impressao?competencia_id={id}`
- `GET /banco-horas/saldo?funcionario_id={id}&data_limite=AAAA-MM-DD`
- `GET /banco-horas/extrato?funcionario_id={id}&data_limite=AAAA-MM-DD`
- `GET /banco-horas/resumo?empresa_id={id}`
- `GET /banco-horas/alertas?empresa_id={id}&dias=30`
- `POST /banco-horas/ajustes`
- `POST /banco-horas/lancamentos/{id}/estornar`

O banco de horas usa o schema 9 e é ativado por escala. Fechamento, lançamentos diários e FIFO pertencem à mesma transação; reabertura estorna a geração da versão anterior e reconstrói as compensações. O contrato, a política para folga insuficiente e as limitações do histórico de escala estão no [relatório de implementação](../RELATORIO-BANCO-DE-HORAS.md). `data_limite` é opcional e filtra a data de referência no ledger atualmente ativo.

`POST /importadores/analisar` detecta automaticamente o adaptador adequado para o arquivo (`.txt` ou `.xlsx`). Nos TXT, os layouts homologados `txt_log_relogio` e `txt_id_tempo_maquina` continuam com prioridade; se nenhum deles reconhecer o conteúdo, entra o fallback `txt_generico`, que tenta localizar semanticamente ID/código/matrícula, nome e data/horário, aceitando aliases de cabeçalho, separadores comuns (TAB, `;`, `|`, `,`), datas brasileiras/ISO, UTF-8/UTF-16/CP1252 e linhas livres estruturadas. O fallback ignora linhas de rodapé/metadados que não contenham identificação e horário suficientes, em vez de inventar dados. Os XLSX continuam nos adaptadores `xlsx_ponto_generico` e `xlsx_cartao_ponto`. Todos compartilham a mesma regra de interpretação de batidas (`app/importadores/interpretacao_batidas.py`): 4 horários = normal, 2 = pendente (só entrada/saída), qualquer outra quantidade = pendente sem inventar qual horário é qual. A confirmação persiste somente registros válidos e selecionados; funcionário desconhecido, data fora da competência e reimportação permanecem conflitos explícitos, e `MarcacaoPonto.origem`/`batidas_originais` preservam qual adaptador interpretou cada marcação.

A primeira apuração, relatório ou tentativa de fechamento gera, de forma idempotente, os dias ainda ausentes da competência para cada funcionário ativo. Dias sem batidas continuam visíveis para conferência; domingos e sábados sem expediente seguem a escala vinculada ao funcionário.

O status da competência é controlado pelas ações de fechamento e reabertura. Uma competência fechada continua disponível para consulta, download e exportação, mas rejeita importações, uploads e edições até ser reaberta.

## Testes

A partir da raiz do projeto:

```bash
.venv/bin/python -m unittest discover -s backend/tests -v
.venv/bin/python -m compileall -q backend/app backend/tests seed_demo.py
```

No Windows, substitua `.venv/bin/python` por `.venv\Scripts\python.exe`.

O escopo congelado e as evidências de aceite estão no [checklist do MVP](../CHECKLIST-CONGELAMENTO-MVP.md).
