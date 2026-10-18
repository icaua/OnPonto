# Etapa 1 — Estabilização e Integridade

Validação local em 18/10/2026. Escopo: tarefas A, B e C de `01_ESTABILIZACAO_P0.md`.
Etapas 2 e 3 não executadas. Nenhuma alteração de dados da instalação ou merge.
A publicação da branch e a abertura de PR foram autorizadas na homologação final.

## Estado inicial

- Checkout limpo na branch `codex/onponto-motor-arquitetura-v2`.
- HEAD: `a80f7d1ca3777154ddf8c9f6d7bd173a27fb78d0`.
- O merge auditado `075f8b8a5d0c2b5278a0c0dad2769fcdc0c2f194` tem HEAD como pai e a mesma árvore: `git diff HEAD 075f8b8` vazio, divergência de commits `0 / 1`.
- Branch de trabalho criada: `codex/fix-p0-stability`, a partir do checkout existente.
- Nenhuma instrução `AGENTS.md` encontrada no repositório ou nos diretórios ancestrais.
- Baseline executado antes das correções: **425 testes Python aprovados** no Windows, Python 3.12.10.

## Diagnóstico e reprodução anterior à correção

### Cobertura histórica

`gerar_dias_faltantes` consultava somente `Funcionario.ativo = True`; `indicadores`
aplicava o mesmo filtro antes de contar lacunas. O calendário já possuía limites
inclusivos de admissão/demissão e resolução histórica de escalas, mas o filtro
cadastral impedia que essas regras fossem aplicadas aos inativos.

Com vínculo fictício de 10 a 15/06/2026 e `ativo=False`, a contagem retornava **0**
em vez de **6** dias ausentes. Para vínculo cobrindo junho inteiro, retornava **0**
em vez de **30**. Com um dia regularizado e cinco ausentes, as lacunas eram
ignoradas. A mudança cadastral para inativo podia transformar a competência em
`conferida`, apesar das lacunas. Os testes novos reproduziram esses resultados
antes das alterações no aplicativo.

A apuração completa e a triagem já compartilham `indicadores`; o fechamento consulta
a apuração completa, sem depender do cache. O cadastro sincroniza competências
abertas pela triagem. Corrigir os dois filtros cobre esses consumidores sem
alterar as fórmulas financeiras, DSR ou as regras de fechamento.

### Windows e CI

Os jobs e os logs de [38061474809](https://github.com/icaua/OnPonto/actions/runs/38061474809)
foram consultados: Ubuntu aprovado; Windows com três falhas entre 425 testes.
As três falhas foram reproduzidas localmente usando `GetShortPathNameW` e uma raiz
temporária 8.3 real; os mesmos testes passavam usando a raiz longa.

- Backup: comparação textual do caminho encontrado com a mensagem de log, embora
  alias e nome longo apontassem para o mesmo arquivo.
- Upload/download e restauração: `is_relative_to` entre caminhos com representações
  diferentes, sem resolver ambos os lados.

As validações da aplicação já resolviam a raiz e o arquivo. Portanto, esses três
defeitos estavam nas asserções dos testes. A matriz existente em
`.github/workflows/tests.yml` permanece adequada e não foi modificada.

### Limpeza e transações

Falhas injetadas em dados sintéticos comprovaram três defeitos adicionais:

- `OSError` na validação de conteúdo deixava o arquivo recém-escrito no disco.
- Falha no commit da auditoria de reenvio escapava sem rollback e sem tradução
  para erro HTTP controlado.
- Restauração com referência sem mapeamento ou falha na verificação final deixava
  o diretório de destino parcialmente restaurado.

## Alterações e compatibilidade

- A geração e a contagem agora compartilham a elegibilidade do calendário:
  ativos mantêm o contrato anterior; inativos com admissão e demissão informadas
  participam somente nas datas do vínculo.
- Inativos sem ambos os limites não recebem dias presumidos. Quando as datas
  conhecidas não excluem a competência, recebem `avisos_vinculo`, o contador
  informativo `operacional.vinculos_incompletos` e uma observação no resumo,
  também disponível nos relatórios existentes.
- O aviso de vínculo incompleto, sozinho, não bloqueia o fechamento legado.
  Essa decisão preserva o cenário existente de espelho em lote com inativo sem
  histórico datado. A suíte completa identificou essa incompatibilidade na
  tentativa inicial de bloqueio, que foi corrigida sem alterar o teste legado.
  Lacunas de vínculos comprovados continuam bloqueando com HTTP 409 e motivo legível.
- A reaplicação continua idempotente. Escalas históricas, marcações importadas,
  batidas duplicadas originais, revisões e decisões humanas são preservadas.
- Competências fechadas continuam retornando seus snapshots. O teste cobre tanto
  um fechamento legado com lacunas quanto um fechamento novo com versão preservada.
- As asserções Windows usam `samefile` para o arquivo logado e `resolve` nos dois
  lados para verificar fronteiras de diretório. Nenhuma proteção da aplicação
  contra travessia ou saída da raiz foi relaxada.
- Uploads passam pela mesma fronteira de rollback/limpeza na validação, consulta
  de duplicidade, auditoria e persistência. Falhas internas retornam HTTP 500
  genérico; erros de validação mantêm seus códigos anteriores.
- A restauração reserva exclusivamente um destino novo, limpa esse destino em
  caso de erro e mantém origem e destinos preexistentes intactos.
- Sem mudança de schema, migração, dependências, tolerâncias ou golden master.

## Arquivos modificados

| Arquivo | Finalidade |
| --- | --- |
| `backend/app/calendario/service.py` | Regra compartilhada de elegibilidade histórica. |
| `backend/app/apuracao/service.py` | Geração de calendário para vínculos históricos elegíveis. |
| `backend/app/apuracao/operacional.py` | Contagem histórica de lacunas e avisos explícitos de incerteza. |
| `backend/app/importadores/armazenamento.py` | Limpeza e rollback também em validação e reenvio. |
| `backend/app/database/recuperacao.py` | Limpeza exclusiva do destino novo após falhas. |
| `backend/tests/test_vinculo_historico.py` | 12 testes com limites, inativação, legado, escala, fechamento e preservação. |
| `backend/tests/test_caminhos_windows.py` | Reexecução dos três contratos com alias 8.3 real. |
| `backend/tests/test_backup_automatico.py` | Equivalência semântica do arquivo registrado no log. |
| `backend/tests/test_evidencias_propostas.py` | Paths resolvidos, limites de raiz, symlink e falhas de upload/commit. |
| `backend/tests/test_recuperacao_conjunto.py` | Paths resolvidos, arquivos ausentes, referências inválidas e falhas de restauração. |
| `backend/README.md` | Contrato de calendário histórico e compatibilidade dos legados. |
| `frontend/js/features/store.js` | Preserva os avisos e as observações recebidos da API. |
| `frontend/js/screens.js` | Avisos identificados por funcionário no resumo e observações escapadas. |
| `frontend/js/features/screen-conferencia.js` | Mesmo aviso na conferência, inclusive sem marcações. |
| `frontend/app.js` | Alerta na confirmação de fechamento e texto correto de inicialização. |
| `frontend/index.html` | Versões dos scripts alterados para evitar cache antigo. |
| `frontend/tests/vinculos-historicos.test.cjs` | Quatro regressões de exibição, compatibilidade e fechamento. |
| `docs/ESTABILIZACAO-P0.md` | Diagnóstico, validação e resumo proposto de PR. |

## Validação

Todos os testes usaram SQLite em memória ou bancos e uploads sintéticos em
diretórios temporários. O processo de validação definiu `ONPONTO_DATABASE_URL=sqlite://`
e uma raiz temporária de segurança para `ONPONTO_UPLOADS_DIR`; subprocessos HTTP
dos testes usam seus próprios bancos e uploads temporários.

Comandos na raiz, usando a virtualenv existente:

```powershell
$env:ONPONTO_DATABASE_URL = 'sqlite://'
$env:ONPONTO_UPLOADS_DIR = Join-Path $env:TEMP ('onponto-p0-guard-' + [guid]::NewGuid().ToString())
& .venv\Scripts\python.exe -m unittest discover -s backend/tests -v
node --test frontend/tests/*.test.cjs
& .venv\Scripts\python.exe -m compileall -q backend/app backend/tests seed_demo.py
git diff --check
```

Resultados finais no **Windows**, Python **3.12.10** e Node **24.19.0**:

| Verificação | Resultado |
| --- | --- |
| Suíte Python completa | **445 testes em 65,376 s; 444 aprovados, 1 ignorado, nenhuma falha/erro.** |
| Caso Windows 8.3 | Aprovado; reexecutou os três testes do CI e o teste de falha final de restore com alias real. |
| Suíte Node | **114/114 aprovados**, nenhuma falha ou teste ignorado. |
| `compileall` | Aprovado, saída 0. |
| `git diff --check` | Aprovado. |
| Golden master, modelos e migrações | Nenhuma modificação. |
| CI Linux/Windows | Acompanhar os checks do PR para o SHA publicado; resultados finais registrados na descrição do PR. |

O teste ignorado foi `test_download_e_referencia_recusam_symlink_para_fora_da_raiz`,
porque a criação de symlink não é permitida neste Windows. Os outros casos
negativos executados incluem hash divergente, arquivo fora de uploads, travessia
`..`, diretório vizinho com prefixo semelhante, referência inválida e restauração
com arquivo ausente. Testes de preservação verificam também integridade SQLite,
chaves estrangeiras, migração repetida e evidências/snapshots imutáveis.

Foram adicionados 20 testes descobertos pela suíte: 12 de vínculo histórico,
1 de aliases Windows, 4 de evidências/uploads e 3 de restauração. O caso de
aliases executa adicionalmente os três contratos existentes e a injeção de falha
de verificação final da restauração dentro de sua fixture.

## Revisão e homologação final

Os 12 arquivos originais foram revisados, incluindo as referências consumidoras
do calendário, da triagem, do fechamento e dos relatórios. A revisão encontrou
dois pontos adicionais que foram corrigidos nesta mesma etapa:

1. O normalizador do frontend descartava `avisos_vinculo` e `observacoes`.
   O aviso chegava à API/exportação, mas não ao operador na interface principal.
   Quatro testes Node reproduziram a lacuna antes da correção. Agora o resumo e
   a conferência exibem os nomes afetados, a orientação de revisão cadastral,
   a informação de que não foram presumidos dias e o acesso aos cadastros.
   A confirmação de fechamento repete o alerta, mantendo a decisão da API.
   Textos e nomes são escapados. Snapshots antigos não recebem aviso inventado.
2. O teste de falha final do restore comparava a raiz temporária sem resolução.
   A asserção de injeção agora compara caminhos resolvidos, e o cenário também
   é executado dentro da fixture Windows 8.3.

A correção de apresentação acrescenta seis arquivos frontend ao diff: **18
arquivos no total**. Não houve expansão para arquitetura, performance ou Etapa 2.

Homologação realizada em navegador com API real e banco exclusivamente sintético:

- Junho: inativo com vínculo de 10 a 15/06 expôs seis lacunas; fechamento desabilitado.
- Duas inicializações: seis dias persistidos somente para o vínculo completo;
  nenhum dia criado para os dois legados incompletos.
- Avisos e nomes visíveis no resumo e na conferência, sem precisar exportar.
- Julho: competência com evidência conferida permitiu fechar, exibindo primeiro
  o aviso no diálogo. O snapshot fechado preservou o aviso e a evidência.
- SQLite sintético após o fluxo: `integrity_check=ok`, `foreign_key_check=[]`.
- Capturas locais em `logs/p0-homologacao-*.png`, fora dos arquivos publicados.

Os resultados remotos devem ser associados ao SHA do PR, sem inferir homologação
de um run anterior ou de uma branch diferente.

## Riscos residuais e homologação

- Linux não está disponível neste host. A validação Linux depende do GitHub
  Actions do PR; o sucesso antigo do Ubuntu não homologa este diff.
- O Windows local não permite criar symlinks; esse caso negativo fica condicionado
  à execução em Linux ou Windows com a permissão correspondente. As verificações
  reais de caminhos externos, travessia, prefixo de diretório vizinho e aliases
  8.3 foram executadas no Windows.
- Cadastros inativos sem datas suficientes exigem revisão humana dos avisos;
  as evidências disponíveis não permitem assegurar a cobertura dos dias ausentes.
- Na inicialização explícita de competências abertas antigas, podem aparecer dias
  de inativos que antes eram omitidos. Esses dias precisam da conferência normal.
- Encerramento abrupto do processo ou falha do próprio sistema de arquivos durante
  a limpeza ainda pode deixar resíduos. A correção cobre exceções tratáveis,
  sem introduzir um protocolo novo de recuperação.
- Avisos de depreciação preexistentes de `datetime.utcnow` e `on_event` permanecem
  fora desta etapa.

Homologação manual: em ambiente sintético, criar um inativo com vínculo de
10 a 15/06/2026; conferir que a apuração aponta seis lacunas; inicializar duas
vezes e obter seis/zero criações; conferir os dias e fechar; confirmar que
exportação e consulta preservam o snapshot. Repetir com inativo sem datas e
verificar o aviso sem criação de faltas. Testar download íntegro/adulterado e
restauração para um destino novo, preservando a origem.

Rollback: reverter apenas os arquivos deste diff. Não há migração a desfazer.
Dias já gerados e conferidos devem permanecer no banco; não executar limpeza ou
restauração automática de dados como parte do rollback.

## Resumo proposto de PR

**Título:** Corrige cobertura histórica de inativos e estabiliza integridade no Windows

O calendário e o fechamento ignoravam lacunas de funcionários hoje inativos,
mesmo com vínculo histórico definido. A correção considera as datas do vínculo,
preserva marcações e snapshots e explicita vínculos legados incompletos sem
presumir faltas. Corrige também as três asserções Windows que confundiam aliases
8.3 com caminhos distintos e fecha lacunas de limpeza/rollback em upload e restore.

Validação: testes de regressão com dados sintéticos, suíte Python completa,
114 testes Node, compilação, verificação do diff e navegação com API/banco
sintéticos. Os checks Linux/Windows são acompanhados no PR. Sem merge automático.
