# Melhorias de prioridade alta — 03/10/2026

## Base, backup e preservação

- Trabalho direto na branch `main`, sem worktree, push ou merge.
- Os scripts `instalar_onponto.bat` e `iniciar_onponto.bat` não foram executados no repositório.
- Antes de qualquer alteração, foi criado o ZIP completo, incluindo `.git`, `.venv`, banco e uploads:
  `C:\Users\icaua\Documents\OnPonto-backups\OnPonto_backup_pre_plano_altos_20261003-1314.zip`.
- ZIP com 4.463 arquivos e 95.742.990 bytes; abertura e CRC de todas as entradas verificados com `ZipFile.testzip()`.
- SHA-256 do ZIP: `0e0bc5c8cd9d32decb4eac5a9562f0876e6349c244b7eecfd4883f74cb279af2`.
- Evidências, cópias, scripts de medição, logs e capturas estão em
  `C:\Users\icaua\Documents\OnPonto-backups\validacao_plano_altos_20261003-1314\`.

O banco operacional e os 13 arquivos de uploads ficaram **byte a byte intactos**.
Os hashes finais coincidem tanto com o levantamento inicial quanto com cada arquivo
correspondente dentro do ZIP. O banco operacional continua no schema 12; apenas a
cópia externa foi migrada para 13.

| Conjunto protegido | SHA-256 antes = depois |
| --- | --- |
| `backend/onponto.db` | `ee566798d8d0ab527c8ff801cfb62eaaeb3e4aa22d8264a886b9df6683ec1f4b` |
| Manifesto dos 13 arquivos em `backend/uploads/` | `5b6f3b2639397ecb65aaf91bcb5424c01a8c3ddc7bc56eb330c8ff02cf786698` |

O hash agregado dos uploads usa SHA-256 do JSON UTF-8 que mapeia caminhos relativos
a hashes individuais, com chaves ordenadas, `ensure_ascii=False` e separadores
`(',', ':')`. Os hashes de cada arquivo estão em `hashes_antes.json` e
`hashes_depois.json`; `preservacao-final.json` registra a confirmação com o ZIP.

## Commits locais

| Etapa | Commit | Mensagem |
| --- | --- | --- |
| Passo 0 | `31c3fa9` | `feat: atestado por dias e edicao segura no autosave` |
| Item 1 | `c0bc461` | `feat: backup automatico antes de migrar` |
| Item 2 | `655bb7b` | `perf: escalas da apuracao em memoria` |
| Item 3 | `1e7fb55` | `feat: tela de API indisponivel` |

O passo 0 preservou as quatro alterações pendentes, sem editar seu conteúdo, e foi
commitado após os 88 testes existentes do frontend passarem. Este relatório é
registrado separadamente em um commit de documentação.

## Item 1 — Backup automático

`backend/app/database/backup.py` é chamado no startup antes de `create_all`, das
migrações e da preservação de fechamentos. Somente bancos SQLite existentes em
arquivo recebem cópias; bancos em memória e inexistentes são ignorados.

- Pré-migração: `onponto-v{atual}-antes-da-v{nova}-{AAAAMMDD-HHMMSS}.db`.
  A falha da cópia obrigatória cancela o startup com caminho e motivo do erro.
- Diário: `onponto-diario-{AAAAMMDD}.db`, uma cópia na primeira subida do dia.
  Falhas geram aviso e permitem a inicialização.
- A origem é aberta por URI `mode=ro`. A API `sqlite3.backup` escreve em arquivo
  temporário, verifica `PRAGMA integrity_check` e publica por renomeação.
- Retenção das 10 cópias pré-migração e 7 diárias mais recentes, identificadas por
  nomes próprios e ordenadas pela data. Arquivos manuais não são removidos.
- `ONPONTO_BACKUP_DIR` prevalece. O banco padrão usa `backups/automaticos/`;
  outros bancos usam `backups/` na pasta do próprio banco.
- O módulo registra cada caminho criado em nível INFO. Avisos de falha usam WARNING.
- `exportar_pendrive.sh` exclui `backups/` e remove a pasta de backups de uma
  exportação anterior no destino. O README explica localização e restauração.

Os dez testes novos cobrem ordem anterior à migração, versão/dados/integridade,
diário único, retenção, destino configurado, bancos em memória/inexistentes,
falhas, preservação dos bytes da origem e transações confirmadas em WAL.

Aceite com dados copiados: uma API temporária gerou
`backups/onponto-v12-antes-da-v13-20261003-131953.db` dentro da pasta de validação,
com schema 12 e integridade `ok`; migrou a cópia para 13 e respondeu `status=online`.
Evidências: `item1-aceite.json` e `item1-api.log`.

## Item 2 — Apuração rápida

Os sete testes de caracterização passaram **antes** da alteração do algoritmo.
Cobrem ausência de histórico, um vínculo, troca com limites inclusivos, desempate
por início e ID, lacunas, datas anteriores ao primeiro vínculo e vínculo encerrado.
Após a mudança, verificam tanto a função avulsa original quanto o resolvedor.

`ResolvedorEscalas` carrega histórico e escalas em duas consultas e resolve cada
dia em memória. O objeto dura apenas a operação atual, evitando cache entre
requisições. É compartilhado entre apuração e complementação do banco de horas.
No fechamento, é criado depois de `registrar_vinculo_inicial`. A função avulsa
`escala_no_dia` mantém assinatura e implementação para ajustes manuais e folgas.
Nenhuma regra de cálculo, distribuição, arredondamento ou fechamento foi alterada.

O teste de regressão apura 40 funcionários × 30 dias, com escalas distintas e
funcionários com/sem histórico, exigindo no máximo 300 consultas. Verifica também
as duas consultas do carregamento e zero consultas nas 1.200 resoluções de dias.

### Comparação integral

`medir_apuracao.py`, na pasta de validação, salvou os JSON completos antes/depois,
removendo apenas o campo superior `gerado_em`. As comparações textuais, incluindo
todas as listas e campos, ficaram idênticas:

| Cenário | SHA-256 idêntico dos JSON antes/depois |
| --- | --- |
| Sintético: 4 funcionários × 30 dias, troca em 15/09, políticas mista/banco e créditos anteriores | `c41f3cc1c9ca60f22c2617012201edd88942ef165764f7fc216d86870295e320` |
| Cópia real: todas as competências existentes, 1 competência | `84ce20cdef07fd8f9692138fa447c23098bb7857b936ad3bedb30ca4090965b7` |

Arquivos: `sintetico-antes.json`, `sintetico-depois.json`, `real-antes.json` e
`real-depois.json`. Os dados reais permanecem fora do versionamento.

### Medições

SQLite em memória, 80 funcionários × 30 dias, escala legada sem histórico.
Três execuções em cada versão, com sessões novas. O salvamento executa
`atualizar_marcacao(..., conferido=True)`, incluindo validação, atualização do
status da competência e commit; não mede somente a função de validação.

| Operação | Antes, mediana | Depois, mediana | Faixa depois |
| --- | ---: | ---: | ---: |
| Apuração completa | 2,601 s | 0,321 s | 0,256–0,344 s |
| Salvar dia conferido | 4,140 s | 0,535 s | 0,471–0,593 s |
| Consultas por apuração | 9.609 | 10 | 10 nas três execuções |

As metas de 0,5 s e 1 s foram atingidas em todas as execuções. Por isso,
`validar_conferencia` não foi restringida ao funcionário: o ajuste condicional
previsto no pedido não foi necessário. Evidências: `medicoes-antes.json` e
`medicoes-depois.json`.

## Item 3 — API indisponível

Sem `?demo=1`, a falha de bootstrap passa para `apiMode = "indisponivel"`, esvazia
os dados e o estado de OCR e desenha a tela de conexão antes de qualquer tela de
dados. Ela contém o título e a orientação solicitados, botão “Tentar de novo” e
repetição automática após 5 s. A sidebar de dados e os seletores ficam ocultos.

As tentativas simultâneas compartilham a mesma operação. Quando a API responde,
o bootstrap carrega os dados reais, cancela a repetição e retoma a rota atual sem
recarregar a página. O hash não é normalizado contra uma lista vazia enquanto a
API está indisponível. Não há faixa ou toast de demonstração nessa situação.

`?demo=1` ativa explicitamente `offline` com mocks, inclusive com a API disponível.
A inicialização `Mocks.getFreshData()` foi preservada, assim como os testes em VM
sem `window.location`. Falhas de salvamento no meio da sessão continuam sob o
tratamento existente. Foram atualizados os parâmetros `?v=` de `app.js` e CSS.

Os sete testes novos cobrem dados/HTML sem mocks, demonstração explícita, botão,
repetição em 5 s, retomada da rota, falhas repetidas, deduplicação e VM sem location.

Aceite em Chrome headless, viewport 1366 × 768: com a API desligada, dados vazios e
tela de conexão visível; após iniciar a API com a cópia externa, os dados reais
apareceram em **4,067 s**, sem reload e mantendo a rota. Nenhum erro JavaScript.
O modo demo também foi verificado com a API ligada. A captura da tela indisponível
foi inspecionada visualmente. Evidências: `validar_conexao.cjs`, `item3-aceite.json`,
`item3-api-indisponivel.png` e `item3-api-reconectada.png`.

## Verificações por etapa

| Etapa | Backend | Frontend | Compileall | git diff --check |
| --- | ---: | ---: | --- | --- |
| Passo 0 | — | 88/88 | — | — |
| Item 1 | 338/338 | 88/88 | OK | OK |
| Item 2 | 346/346 | 88/88 | OK | OK |
| Item 3 | 346/346 | 95/95 | OK | OK |

Comandos executados ao fim de cada item:

```powershell
$env:PYTHONUTF8="1"
.venv\Scripts\python.exe -m unittest discover -s backend/tests
node --test frontend/tests/*.test.cjs
.venv\Scripts\python.exe -m compileall -q backend/app backend/tests seed_demo.py setup/instalar_onponto.py
git diff --check
```

Os logs são `passo0-frontend.log` e `item{1,2,3}-{backend,frontend}.log` na pasta de
validação. A caracterização anterior está em `item2-caracterizacao-antes.log`.
O backend cresceu de 328 para 346 testes; o frontend, de 88 para 95.
Nenhum teste existente falhou. Há avisos de depreciação de SQLAlchemy e
`datetime.utcnow`, sem falhas nos testes.

## Limitações e pendências

- Nenhuma pendência de implementação identificada nos três itens.
- O aceite visual foi automatizado em navegador; não foi executado o atalho ou
  instalador da instalação operacional.
- As medições representam o cenário solicitado nesta máquina; não são uma
  garantia de tempo para outros volumes, políticas ou dispositivos.
- Backups automáticos cobrem o banco; uploads continuam exigindo preservação
  conjunta, conforme documentado no README.
- A migração do banco operacional ocorrerá somente na próxima inicialização
  normal, já protegida pelo backup obrigatório.
