# Execução da modernização OnPonto

Especificação principal lida integralmente: `OnPonto_Plano_Mestre_Codex_Arquitetura_Motor.md`.
Início: 10/10/2026. Branch de integração local: `codex/onponto-motor-arquitetura-v2`.
Não haverá merge automático. Somente dados fictícios/temporários são usados nas validações.

## Base e diferenças após auditoria

- Auditoria: `038a3c53bbbb6f67a9320659b7143f86f1c944e1`.
- Main local inicial: `65d5059afb2d24867435129baad7a6482cf1816d`, árvore limpa.
- `git fetch origin main`: remoto em `038a3c5`; main local seis commits à frente.
- Incorporados ao baseline: instalador reproduzível/offline (`a206013`), edição de atestados/autosave (`31c3fa9`), backup automático antes de migrar (`c0bc461`), resolvedor de escalas em memória (`655bb7b`), API indisponível (`1e7fb55`), relatório de prioridades (`65d5059`).
- Arquitetura existente: FastAPI/SQLAlchemy/SQLite, parsers TXT/XLSX, SPA vanilla, ledger e snapshots correntes. Migrações incrementais; sem AGENTS.md aplicável encontrado.

## Checkpoints

| Pacote | Estado | Branch/commit/PR | Testes | Diferenças de cálculo | Benchmark | Bloqueios |
|--------|--------|------------------|--------|-----------------------|-----------|----------|
| 00 | validado | `17c366c` | backend 350/350; Node 95/95; compileall/diff OK; Playwright OK nas duas resoluções | nenhuma | `docs/benchmarks/00-baseline.json`, 3 portes completos | nenhum |
| 01 | validado | `2d9faa6` | backend 357/357; Node 95/95; golden sem regeneração; compileall/diff OK | nenhuma | `01-nucleo-50.json` | nenhum |
| 02 | validado | `12b823e` | backend 363/363; Node 95/95; Playwright nas duas resoluções; golden/compileall/diff OK | regra histórica substitui edição retroativa | `02-versoes-50.json` | nenhum |
| 03 | validado | `ad3025c` | backend 375/375; Node 98/98; Playwright duas janelas; golden/compileall/diff OK | nenhuma trabalhista | `03-revisoes-50.json` | nenhum |
| 04 | validado | `efb9b78` | backend 395/395; Node 101/101; Playwright duas resoluções/duas janelas; golden/compileall/diff OK | intervalo e DSR explícitos; legenda neutra de feriado | `04-intervalos-dsr-50.json` | nenhum |
| 05 | validado | `3bac476` | backend 402/402; Node 102/102; Playwright resumo/conferência; golden/compileall/diff OK | estado operacional inclui dias ausentes/análises | `05-final.json`, 3 portes completos | nenhum |
| 06 | validado | `64d2526` | backend 412/412; Node 102/102; navegador/migração/compileall/diff OK | nenhuma trabalhista; reenvio idempotente | `06-importacao.json`, 3 portes | nenhum |
| 07 | validado | `cbd5fd1` | backend 413/413; Node 108/108; navegador ciclo completo OK | módulos e conferência por funcionário | `07-frontend-50.json` | nenhum |
| 08 | validado | `7e838ec` | backend 415/415; Node 108/108; restore ampliado 4/4 | recuperação/índices/distribuição | `08-indices.json`, `08-custo-indices.json`, `08-final-1000.json` | nenhum |
| 09 | validado | `d3a88cc` | backend 425/425; Node 110/110; navegador completo OK | sessão/origens/arquivos; nenhuma regra trabalhista | `09-seguranca-50.json`; OSV 25 pacotes/0 advisories | nenhum local; CI Linux pendente |

## Pacote 00

Comandos baseline executados com `.venv/Scripts/python.exe` (Python 3.12.14, SQLite 3.53.1):

```text
python -m unittest discover -s backend/tests -v  => 346 testes, OK (37,694 s)
node --test frontend/tests/*.test.cjs            => 95 testes, OK
python -m compileall -q backend/app backend/tests seed_demo.py => OK
node frontend/tests/conferencia-browser.cjs     => OK
```

Playwright com bibliotecas do runtime: 1366×768 (9 linhas visíveis), 1920×1080 (17 linhas); sem overflow horizontal ou erro JS. Identidade, busca, atribuição de batida, autosave, auditoria e undo aprovados. Capturas em diretório temporário fictício. Nenhuma falha herdada observada.

Checkpoint 00 concluído: 350 testes backend (37,334 s), 95 Node, compileall e diff check aprovados. Golden master estruturado inclui mês aberto, fechamento, reabertura/refechamento, ledger com estornos e compensações e valores Excel. Fixture de dois arquivos conflitantes verifica preservação da primeira evidência e ambos os arquivos. Recuperação offline testa restauração sem sobrescrita, migração repetida de schema antigo, hashes adulterados e FK/integridade. Suites legadas de migração/backup também passaram. CI Windows/Linux adicionado; job ainda não executado no GitHub.

Benchmark HTTP dos três portes terminou com status 200 em todas as operações medidas, usando 3.050, 15.250 e 61.000 marcações fictícias. Metodologia e limites em `docs/benchmarks/README.md`. Nenhum ganho de performance é alegado no pacote 00. Sem alteração de schema, frontend ou regras. Primitiva de backup/restore ainda não remapeia caminhos absolutos para outra instalação, pendência expressa do pacote 08.

Próximo pacote autorizado pela dependência: 01, núcleo puro e adaptadores equivalentes ao golden master. DSR no pacote 04 depende da definição solicitada ao usuário; não há implementação existente a preservar nem fórmula fornecida pelo plano. Ver ADR 0001.

Rollback: reverter os commits da iniciativa; não manipular DB/uploads reais. OCR funcional permanece fora do escopo.

## Pacote 01

Núcleo puro extraído, dataclasses e adaptadores adicionados, classificação do dia compartilhada. Motor importa com `python -S`, sem FastAPI, SQLAlchemy ou banco. Resultado incompleto/indisponível usa `None` no domínio; API legada preserva campos e números existentes acompanhados de pendências. Nenhuma mudança de schema/endpoints/frontend.

Backend: 357 testes OK (36,564 s); Node: 95 OK; compileall e diff check OK. Golden master completo passa sem regeneração. Tabela de tolerâncias, falta/atestado, cronologia, feriado, ocorrência parcial sem referência e ausência de escala testados. Benchmark HTTP 50 executado com o mesmo harness e runtime; consultas mantidas em 340 para GET /apuracao. Nenhum ganho de performance alegado. ADR 0002 registra limites e rollback. Pacote 02 liberado pela dependência.

## Pacote 02

Migração aditiva 14: `escala_versoes`, configuração JSON imutável, limites de validade, origem de vigência desconhecida, índices/triggers contra sobreposição e exclusão; `escalas.jornadas_semana_json`. Resolvedor por data aplicado à apuração, calendário e banco. PUT/PATCH de escala cria versão, aceita `vigente_desde`, invalida conferência dos dias abertos afetados e recusa vigência sobre fechamento. GET `/escalas/{id}/versoes` expõe histórico. Formulário preserva visual e informa vigência futura; jornadas detalhadas por dia disponíveis na API.

Diferença deliberada: edição posterior deixa de recalcular meses antigos com a configuração corrente. Regra desconhecida antes da migração permanece explicitamente desconhecida; não se inventaram versões anteriores. Testes de setembro/outubro, sábado 240 minutos, precedência de feriado/domingo, preservação byte a byte de snapshot, conflito, idempotência e integridade passam. Golden existente não foi regenerado. Fixtures de banco que configuram ORM diretamente passaram a criar cadastro legado sem versão, preservando seus resultados esperados; API e temporalidade são cobertas por testes próprios. Nome esperado de backup usa SCHEMA_VERSION; consulta em lote passou de 2 para 3 devido ao carregamento de versões, sem consulta por dia.

Medição 50: GET usa 341 queries, com 1.385/1.128/1.196 ms. Todas as operações HTTP medidas deram 200. Não há ganho alegado: otimização cabe ao pacote 05. Playwright nas duas resoluções passou, incluindo autosave, undo e auditoria. ADR 0003 contém decisão e limites de rollback. Nenhuma migração foi aplicada ao DB real.

Checkpoint final: 363 testes backend OK (38,538 s), 95 Node OK, compilação e diff check OK. Vigências futuras sucessivas não reescrevem a configuração agendada. Pacote 03 liberado.

## Pacote 03

Migração 15, fechamentos/reaberturas append-only, revisão otimista e unidades transacionais implementadas. Histórico consultável em `/competencias/{id}/fechamentos`. Nova revisão obrigatória para mutações HTTP de marcações; frontend envia token, suspende conflito e oferece comparação/escolha explícita. Confirmação de importação perdeu commit intermediário; original continua preservado. ADR 0004 documenta contratos e rollback. Golden não regenerado; apenas revisão de transporte excluída da comparação de cálculo.

Checkpoint: 375 testes backend OK (47,284 s), 98 Node OK, compileall/diff OK. Playwright 1366×768 e 1920×1080 passou com duas janelas, 409 e escolha explícita de recarga sem nova escrita. HTTP concorrente confirmou um vencedor por revisão, PATCH tardio recusado, lote obsoleto integralmente recusado e exclusão entre fechamento e upload. Falhas simuladas em fechamento, reabertura, lote e confirmação preservaram todo o estado anterior. Migração repetida preservou bytes, marcou ausência de snapshot legado, FK vazio e integridade OK. Todas as operações do benchmark 50 deram 200; sem ganho de desempenho alegado. Pacote 04 liberado pelas dependências e política de DSR definida.

## Definição de DSR recebida

Usuário definiu domingo e feriado como padrão, com dia de descanso configurável na escala. Política confirmada: os seis dias anteriores ao descanso são a referência; uma ou várias faltas injustificadas descontam no máximo um descanso semanal; atestados, abonos, atrasos e faltas justificadas não causam perda; feriados do mesmo período também são descontados. Unidade: dias de descanso/feriado, sem conversão salarial inventada. Pacote 04 implementará configuração explícita versionada e fixtures de fronteira mensal; escala legada não receberá desconto silencioso.

## Pacote 04

Migração aditiva 16 e ADR 0005: intervalo fixo/flexível/sem intervalo, registro real/pré-assinalado, jornadas próprias e DSR versionados. Pré-assinalação nunca altera originais nem completa batida parcial. Falta justificada com motivo, descanso configurável, seis dias de referência, perda limitada a um descanso e feriados aplicáveis. Dados futuros ausentes deixam desconto indisponível e bloqueiam fechamento. Referências entre competências são guardadas no snapshot e protegidas contra edição de marcação, ocorrência, calendário, vínculo ou escala até reabertura. Versões fechadas permanecem imutáveis.

Backend 395 testes OK (51,019 s), Node 101 OK; Playwright 1366×768 e 1920×1080 passou com duas janelas, autosave e resolução explícita de 409, sem overflow/erro JS. Compilação e diff OK. Após remoção de bloco redundante de migração, suite DSR/migração (7) repetida com sucesso. Integração verifica resultado diário/resumo/ledger/Excel/espelho, adicional 60%, destinação 50/50, originais sem preenchimento sintético, tolerâncias, atestado integral/parcial, sábado 240 e referência cruzando mês. Golden não regenerado: somente dois cabeçalhos Excel antigos são normalizados para a legenda neutra “Horas em feriado”, com valores, snapshots e ledger intactos. Quatro expectativas antigas de enum/legenda foram atualizadas deliberadamente; nenhum resultado numérico mudou.

Benchmark 50: GET 341 queries, 1.349/1.177/1.245 ms; PATCH 361 queries, 2.170 ms; fechamento 730 queries, 2.734 ms. Todas as operações HTTP deram 200. Sem ganho alegado; pacote 05 tratará consultas e triagem. Migração aplicada apenas a DB fictício; rollback conforme ADR 0005, sem downgrade sobre dados reais. Pacote 05 liberado pelas dependências.

## Pacote 05

Migração aditiva 17: cache de contadores por competência/funcionário com assinatura do contexto, escrito apenas nas mutações. Contexto de apuração compartilhado entre dia/conferência/motor integral; ledger e vínculos carregados em lotes, cortes e compensações preservados. Fechamento recalcula integralmente sob transação e ignora cache; foi retirada apenas a segunda apuração redundante dentro da mesma transação. Endpoints `/apuracao/resumo`, `/apuracao/triagem` e `/apuracao/dias` adicionados. Frontend de resumo não busca marcações/arquivos nem aceita resumo compacto como detalhes da conferência. Cache DSR inclui fontes de outro mês.

Diferença operacional deliberada: dias do vínculo sem registro e análises não confirmadas impedem o status `conferida`. Expectativa do teste de ciclo de estados foi corrigida; inicializar e conferir o restante continua liberando esse status. Fluxos de marcação, ocorrência, calendário, cadastro, escala e confirmação sincronizam estados abertos. Nenhuma regra trabalhista alterada. FIFO, ciclos, vencimentos, estornos, snapshot e valores Excel iguais ao golden sem regeneração. Excel mantém células/formatos e substitui varredura de max_row por contador.

Validação final: 402 testes backend OK (48,153 s), Node 102 OK, compileall/diff OK. Playwright nas duas resoluções passou conferência, duas janelas/409 e painel resumido sem requisição de milhares de dias, sem overflow/erro JS. Novos testes verificam equivalência dos contadores, GET sem efeitos, invalidação apenas da pessoa alterada, referência DSR entre meses, fechamento independente de cache adulterado, dias/resumo iguais ao motor/snapshot e origem de muitos arquivos em uma única consulta. Mock de falha FIFO aceita o novo argumento de carregamento e ainda verifica rollback após a reconciliação real.

Medição com código estabilizado (hash verificado entre portes): todas as operações HTTP 200 em 50/250/1.000 pessoas. GET 12 queries nos três portes (baseline 340/1.670/6.670); PATCH subsequente 30 queries; triagem aquecida 11; dias de uma pessoa 11. Em 1.000: GET mediano 19.621→14.443 ms; primeiro PATCH 31.744→16.259 ms; fechamento 41.169→22.615 ms; Excel 159.886→39.816 ms; reabertura 20.745→5.179 ms. Resumo sem dias reduz payload em 98,0%. Comparação e limites em `docs/benchmarks/05-comparacao.md`; execução intermediária preservada. Não são percentis de produção nem RSS.

ADR 0006 registra contratos, invalidadores e rollback. Cache é descartável; cold start ainda avalia o mês, conferência integral permanece disponível até refatoração gradual do pacote 07. Dados reais, main e arquivos originais não foram manipulados. Pacote 06 liberado.

## Pacote 06

Schema aditivo 18 e ADR 0007: armazenamento/parser/proposta separados, revisão de prévia preservada, hash real, contexto e versão de adaptador. Confirmação não reinterpreta arquivo e exige revisão HTTP; cadastro/regras/conteúdo/adaptador alterados bloqueiam a proposta obsoleta. Reenvio retorna resultado preservado e upload igual reutiliza apenas original com hash verificado. Consultas de pessoas/marcações em lote. N eventos brutos guardam duplicidades e índices, com linha/ordem física nos TXT que as fornecem, aba/linha/coluna XLSX e informação desconhecida explicitamente ausente no legado. Auditoria e documentos append-only; anexos sucessivos preservados. Inventário somente leitura; contrato de OCR documentado sem endpoint/dependência funcional.

Validação: 412 backend OK (56,856 s), 102 Node OK, Playwright 1366×768 e 1920×1080 OK; compileall e diff OK. Após acrescentar proteção SQL ao JSON original preenchido, 10 testes de evidência e 4 de migração repetidos com sucesso. Proposta sem parser, reenvio, arquivo duplicado, associação corrigida, revisão/cadastro/hash/adaptador obsoletos, rollback, duplicidade e triggers, backfill idempotente com FK/integridade, inventário e ZIP adversarial cobertos. Golden não regenerado. Três expectativas de reenvio foram alteradas deliberadamente: retorno do resultado preservado em vez de novos conflitos, sem nova escrita nem perda da edição humana.

Medição local sintética de importação com 50/250/1.000 pessoas e quatro batidas: análise 62,6/113,9/379,7 ms; confirmação 127,1/338,3/1.355,9 ms, 30 SELECTs nos três portes; reenvio 4,8/8,6/22,1 ms e 12 comandos SQL. SQL total inclui INSERT/UPDATE das evidências; tempo sem tracing não é diretamente comparável ao benchmark HTTP anterior. Originais, eventos e contagens verificados ao final, apenas DB/uploads fictícios. Resultados em `docs/benchmarks/06-importacao.json`.

Rollback preserva tabelas/evidências novas; restauração em destino novo, sem downgrade destrutivo. Endpoints GET `/importadores/{id}/previa` e confirmação com `revisao_previa` documentados no ADR. Main permanece sem merge e DB real intacto. Pacote 07 liberado pelas dependências.

## Pacote 07

Onze módulos exportados, wrappers compatíveis e ADR 0008. Triagem/dias por funcionário substituem carregamento integral na conferência; registros/revisões e cálculo oficial chegam na mesma leitura. Grade reutiliza nós, preserva foco/rolagem, autosave/undo/atalhos e originais. Filas, sequências e revisão protegem respostas antigas; troca de contexto espera persistência e recusa nova edição durante flush. Cálculo online local não afirma minutos definitivos. Reabertura aguarda PATCH; mensagens locais distinguem edição de persistência. Demo explícito continua separado e OCR simulado só é aceito na demonstração.

Backend 413 testes OK (59,214 s); Node 108 OK; compileall/diff OK. Playwright: 1366×768 (9 linhas), 1920×1080 (17), foco/nó/rolagem preservados, duas janelas/409, importação e conferência até fechamento, exportação Excel e reabertura em ambas, sem overflow/erro JS. Correções no roteiro aguardam bootstrap e limitam seletores ao diálogo; nenhum resultado esperado de cálculo foi alterado. Golden não regenerado. Benchmark 50: triagem 11 queries, pacote de uma pessoa 12 queries/52.522 bytes/56,99 ms; todas operações 200. Campo `registros` é aditivo, sem schema/migração. Rollback por revert, sem tocar DB. Pacote 08 liberado.

## Pacote 08

Schema 19: dois índices escolhidos por EXPLAIN e tempos locais, sem remover índices legados. Candidato de ordenação mensal rejeitado por regressão; ledger sem índice novo por falta de ganho. Timeout 10 s/FK explícitos e optimize limitado pós-migração. WAL testado em SQLite 3.53.1, com leitura concorrente, exclusão de escritores e backup consistente; journal padrão preservado. ADR 0009 e manual RECUPERACAO-DISTRIBUICAO registram limites.

Conjunto v2 verifica DB/uploads/referências/hashes/FK/integridade antes de copiar; destino inexistente obrigatório. Restore remapeia apenas caminhos operacionais na cópia, mantém referências históricas através de mapa externo e registra hash final. Teste em outra pasta compara documentos/batidas/auditoria/versões/snapshot fechado/ledger/compensações byte a byte e repete migração; fonte permanece igual. Travessia adulterada é recusada antes de criar destino. Conjuntos v1 antigos devem ser regenerados como v2 para mudar caminhos.

Dependências fixadas e reinstaladas offline da distribuição existente; pip check OK. SQLAlchemy efetivamente carregado agora 2.0.52, igual ao manifesto (antes o diretório tinha módulo 2.1.1 e metadata 2.0.52). Instalador mantém fallback offline→internet nas mesmas versões, sem atualização silenciosa para faixas. SHA256SUMS e testes do instalador passam; binários preservados. Windows validado; Linux não executado localmente, CI preparado.

Backend 415 testes OK (59,331 s), Node 108 OK; restore ampliado 4 testes repetidos OK; compileall/diff OK; golden intacto. Índices: referências de 25 arquivos/30.000 linhas 10,375→0,054 ms, vínculo 0,0535→0,0436 ms; DB 135.380.992→136.409.088 bytes (+0,76%). Confirmação em 1.000 pessoas/um dia elegível mediana 1.453,807→1.468,710 ms (+1,0%); fechamento 440,769→440,493 ms. Análise varia 408,509→454,784 ms; sem promessa de ganho global. Não são percentis de produção. Rollback conforme ADR; DB real não aberto/migrado.

Checkpoint final: benchmark HTTP de 1.000 funcionários/61.000 marcações concluído, todas operações 200, com hash do código estável e dependências fixadas. Resultado integral em `08-final-1000.json`; não comparar sua latência diretamente ao runtime anterior sem considerar a diferença de versões. Pacote 09 liberado.

## Pacote 09

Sessão local/origem/Host/loopback, cookie HttpOnly/SameSite Strict, CSRF por sessão e renovação deduplicada. CORS fechado às origens explícitas; root/health do instalador preservado. Domínio, anexos, arquivos e relatórios exigem sessão. Cliente de integração usa a sessão real; testes negativos usam urllib sem autenticação automática. Frontend e exportação usam credentials, sem token em URL/localStorage. Segurança e limites em ADR 0010/SEGURANCA-LOCAL.md.

Upload genérico compartilha armazenamento/evidência/hash da importação; 25 MiB por arquivo/26 MiB de corpo, assinatura/conteúdo/dimensões, caminhos contidos e nomes sanitizados. ZIP com bombas/duplicidades/DTD/entidades/compressão não homologada é recusado antes do parser. PDF tem validação e descompressão limitada, sem OCR/texto/renderização. Hash conhecido adulterado impede download; legado sem hash continua identificado. Colisão de nome não pode remover o original: teste específico passou. TXT UTF-16 com/sem BOM preservado após detectar e corrigir rejeição inicial na revisão de compatibilidade. Novos controles recusam conteúdo inseguro explicitamente; não alteram bytes dos originais aceitos.

Privacidade: no-store/nosniff/frame/referrer/CSP, SQL sem parâmetros em mensagens de erro e falhas inesperadas com classe somente no log. Retenção herdada de backups auditada/documentada; não se criou exclusão de originais/anexos/snapshots. Levantamento OSV de 2026-10-10 (nomes/versões apenas): 25 pacotes/zero advisories retornados, JSON preservado. Não há certificação de segurança ou alegação de auditoria do SO/binário Python.

Validação final: backend 425 testes OK (63,440 s), Node 110 OK, compileall/pip check/diff OK. Golden completo não regenerado. HTTP negativo cobre sessão/origem/Host/preflight/CSRF/expiração/limite pré-parser, upload adversarial e recuperação preservada. Playwright com sessão real: ambas resoluções, 9/17 linhas, nó/foco/rolagem, autosave/undo, duas janelas/409, importação/conferência/fechamento/Excel/reabertura sem overflow ou erros JS. Capturas fictícias inspecionadas; CSS original preservado.

Benchmark 50 com código final estável: todas operações 200; GET 12 queries, dias por pessoa 12/53,63 ms, PATCH aquecido 31/228,23 ms, fechamento 136/1.197,68 ms, Excel uma consulta/2.232,42 ms. Segurança não introduz consultas SQL por sessão. Números locais com tracing, sem promessa de percentis. Sem nova migração além do schema 19 do pacote 08. Rollback conjunto frontend/backend, preservando novas evidências; manter loopback.

## Encerramento local e pendências externas

Pacotes 00–09 implementados e validados na ordem, com checkpoints independentes. Main local permanece `65d5059afb2d24867435129baad7a6482cf1816d`; sem merge/push, PR ou migração sobre DB/uploads reais. OCR funcional não implementado; somente contratos. A branch contém motor/versões/revisões/evidências/triagem/frontend/recuperação/segurança e documentação de decisões/rollback.

Pendência externa: executar CI em Linux e revisão da branch antes de integração/publicação ampliada; não há credenciais ou pedido de publicação nesta tarefa. Homologação local Windows concluída, sem regressão não resolvida ou bloqueio de dados. Avaliar implantação somente após backup completo e restauração verificada da instalação específica, sem usar dados reais nos testes automatizados.

Commits finais: 07 `cbd5fd1`, 08 `7e838ec`, 09 `d3a88cc`; este registro documental fecha o acompanhamento. Branch `codex/onponto-motor-arquitetura-v2`. Nenhum merge em main foi realizado.
