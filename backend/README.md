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
- `GET/POST /importadores/ignorados`, `DELETE /importadores/ignorados/{id}`
- `GET/POST/PATCH /marcacoes`
- `POST /marcacoes/{id}/batidas-desconsideradas`, `DELETE /marcacoes/{id}/batidas-desconsideradas/{indice}`
- `GET /apuracao?competencia_id={id}`
- `GET /relatorios/excel?competencia_id={id}`
- `GET /relatorios/impressao?competencia_id={id}`
- `GET /banco-horas/saldo?funcionario_id={id}&data_limite=AAAA-MM-DD`
- `GET /banco-horas/extrato?funcionario_id={id}&data_limite=AAAA-MM-DD`
- `GET /banco-horas/resumo?empresa_id={id}`
- `GET /banco-horas/alertas?empresa_id={id}&dias=30`
- `POST /banco-horas/ajustes`
- `POST /banco-horas/lancamentos/{id}/estornar`

O banco de horas usa o schema 12 e aceita políticas por escala: folha, banco ou divisão percentual, adicionais, fatores por tipo de dia e ciclos. O booleano anterior permanece compatível quando `politica_horas` é nula. Fechamento, lançamentos diários, FIFO 1:1 por ciclo e snapshot pertencem à mesma transação; reabertura estorna a geração anterior e reconstrói as compensações. Os novos fechamentos congelam regras e saldos. `data_limite` filtra o ledger atualmente ativo no extrato. Contratos, arredondamento e limites estão no [relatório de confiabilidade e políticas](../RELATORIO-CONFIABILIDADE-E-POLITICAS.md); a implementação anterior está documentada no [relatório do ledger](../RELATORIO-BANCO-DE-HORAS.md).

`POST /importadores/analisar` detecta automaticamente o adaptador adequado para o arquivo (`.txt` ou `.xlsx`). Nos TXT, os layouts homologados `txt_log_relogio` e `txt_id_tempo_maquina` continuam com prioridade; se nenhum deles reconhecer o conteúdo, entra o fallback `txt_generico`, que tenta localizar semanticamente ID/código/matrícula, nome e data/horário, aceitando aliases de cabeçalho, separadores comuns (TAB, `;`, `|`, `,`), datas brasileiras/ISO, UTF-8/UTF-16/CP1252 e linhas livres estruturadas. O fallback ignora linhas de rodapé/metadados que não contenham identificação e horário suficientes, em vez de inventar dados. Os XLSX continuam nos adaptadores `xlsx_ponto_generico` e `xlsx_cartao_ponto`. Todos compartilham a mesma regra de interpretação de batidas (`app/importadores/interpretacao_batidas.py`): 4 horários = normal, 2 = pendente (só entrada/saída), qualquer outra quantidade = pendente sem inventar qual horário é qual. A confirmação persiste somente registros válidos e selecionados; funcionário desconhecido, data fora da competência e reimportação permanecem conflitos explícitos, e `MarcacaoPonto.origem`/`batidas_originais` preservam qual adaptador interpretou cada marcação.

A confirmação da importação ou POST /competencias/{id}/inicializar-calendario gera, de forma idempotente, os dias ainda ausentes da competência para cada funcionário ativo. Consultas de apuração e relatórios não gravam dados. Dias sem batidas continuam visíveis para conferência; domingos e sábados sem expediente seguem a escala vinculada ao funcionário.

O status da competência é controlado pelas ações de fechamento e reabertura. Uma competência fechada continua disponível para consulta, download e exportação, mas rejeita importações, uploads e edições até ser reaberta.

## Testes

A partir da raiz do projeto:

```bash
.venv/bin/python -m unittest discover -s backend/tests -v
.venv/bin/python -m compileall -q backend/app backend/tests seed_demo.py
```

No Windows, substitua `.venv/bin/python` por `.venv\Scripts\python.exe`.

O escopo congelado e as evidências de aceite estão no [checklist do MVP](../CHECKLIST-CONGELAMENTO-MVP.md).

## Identidade de exibição e Conferência

O schema 12 acrescenta `nome_exibicao` e `codigo_exibicao` opcionais aos funcionários.
Os campos `nome` e `codigo` preservam a identidade de origem; importar continua usando
as regras anteriores de associação, nunca o ID de exibição. `GET /funcionarios?q=...`
busca nas quatro identidades, sem distinguir maiúsculas ou acentos. As respostas também
incluem `nome_apresentacao` e `codigo_apresentacao`, com fallback para a origem.

`GET /apuracao` mantém `resumo[].problemas` como fonte das contagens por funcionário e
acrescenta `marcacoes[].problema_rotulo` e `bloqueante` para apresentação. A atribuição
assistida de batidas usa o `PATCH /marcacoes/{id}` existente, com a mesma auditoria.
Veja `RELATORIO-UX-CONFERENCIA.md` na raiz para escopo, validação e limitações.

## Destino das batidas e pessoas ignoradas no relógio

O schema 13 acrescenta `marcacoes_ponto.batidas_desconsideradas_json` e a tabela
`identificacoes_ignoradas`. Nenhuma das duas reescreve batidas originais ou arquivos.

Toda batida bruta precisa de destino: um dos quatro horários ou uma desconsideração
justificada. Dia com ocorrência integral (atestado, férias, afastamento, folga
compensatória) e horários vazios não exige destino; as brutas ficam só como registro.

- `POST /marcacoes/{id}/batidas-desconsideradas` com `{indice, justificativa}` (mín. 10
  caracteres) tira uma batida da contagem, por exemplo uma duplicada. O dia precisa estar
  reaberto e a competência editável; o evento entra no histórico do dia.
- `DELETE /marcacoes/{id}/batidas-desconsideradas/{indice}` restaura a batida.
- `GET /importadores/{arquivo_id}/pendencias-agrupadas` agrupa as pendências de
  importação por pessoa do relógio, sem gravar nada.
- `GET /importadores/ignorados?empresa_id={id}` lista as pessoas ignoradas.
- `POST /importadores/ignorados` com `{empresa_id, codigo_origem, nome_origem,
  justificativa}` ignora uma pessoa nas importações da empresa (ex.: gestão que não
  apura ponto). Os registros dela nas competências abertas viram exclusões justificadas
  com a regra de origem, e as próximas análises aplicam a mesma decisão. O código do
  relógio identifica a pessoa; o nome só decide quando falta código. Funcionário
  cadastrado sempre prevalece, e a regra é recusada quando já existe cadastro com a
  mesma identificação.
- `DELETE /importadores/ignorados/{id}` desativa a regra e devolve às pendências o que
  ela excluiu nas competências abertas. Competências fechadas não são alteradas.

Arquivo cuja análise não deixa registro pendente (por exemplo, só com pessoas ignoradas)
fica `confirmada` automaticamente, sem bloquear o fechamento.

A desconsideração é recusada (HTTP 409) quando o horário continua em uso e não há
outra batida original disponível no mesmo minuto. Duplicatas são tratadas por índice.
A apuração também bloqueia esse conflito em decisões já salvas e exige tratamento
quando restam mais batidas do que campos preenchidos, inclusive com quatro campos.
Correções manuais de horários continuam permitidas e auditadas. O frontend só envia
a desconsideração ou restauração depois de confirmar o salvamento dos horários.
Excluir registros de pessoas não cadastradas do arquivo, ou ignorar essas pessoas
com justificativa, continua liberando o fechamento após conferir os dias cadastrados.
