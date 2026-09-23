# Relatório de correção — Resumo, admissão e Calendário

Data: 12/09/2026. Resultado: três frentes implementadas; **219 testes passaram, zero falhas**.

## Análise inicial

- O aviso de fechamento usava elementos em linha, sem separar título e descrição. Nome e código estavam em um `th`, enquanto o CSS de texto secundário atendia apenas `td`.
- O cadastro não possuía admissão. O motor gerava todos os dias do mês sem verificar o início do vínculo.
- Feriados existiam como situação do dia, mas faltava uma fonte global. Empresa já possuía cidade e UF estruturadas, reaproveitadas nesta implementação.

## Correções visuais

- Aviso compacto de fechamento com ícone, fundo verde discreto, título e duas linhas de descrição.
- Nome e código em linhas distintas; código menor e secundário.
- Situações no mesmo componente: conferido verde, pendente amarelo, erro/bloqueio vermelho, neutro cinza.
- Medição no navegador: badges com 28 px de altura, padding de 4 × 8 px, raio de 4 px, gap de 6 px e células com padding de 12 px.
- “Indisponível” em cor secundária e peso normal; competência com badge junto ao título, sem repetição no cartão de indicadores.

## Data de admissão

- **Model/migration:** `Funcionario.data_admissao` usa `Date`, aceita nulo e não recebe data inventada.
- **API/schema:** criação, consulta e edição; omitir no PATCH preserva o valor, enviar `null` permite limpar. Datas inválidas são rejeitadas.
- **Interface:** campo opcional na criação/edição e coluna Admissão na lista de funcionários.
- **Motor:** elegibilidade centralizada em `calendario/service.py`, consultada antes de gerar dias e antes dos cálculos e ocorrências. O predicado admite um futuro limite final, sem implementar desligamento agora.
- Dias anteriores não entram em dias processados, jornada, faltas, atrasos, extras ou atestados. Admissão posterior à competência deixa os totais zerados e a situação “Fora do vínculo”.
- Batidas anteriores são preservadas com o aviso **“Marcação anterior à data de admissão”**. Essa inconsistência real permanece para conferência, inclusive se o registro estiver marcado como conferido; ela não gera jornada.
- Ao alterar a admissão, apenas placeholders automáticos vazios, intocados e sem histórico são removidos do período anterior. Registros importados, decisões manuais e históricos permanecem guardados.
- **Testes:** admissão em 01/06 → 30 dias; em 18/06 → 13 dias; em 10/07 → nenhum dia em junho; batida em 15/06 preservada; admissão nula mantém o comportamento anterior.

## Calendário

- Menu global **Calendário**, rota `#/calendario`, independente de empresa ou competência selecionada.
- Lista anual com filtros de ano, tipo e abrangência; criação, edição e desativação. O formulário permite reativar uma data.
- Entidade com nome, data, tipo, descrição, abrangência, UF, município, empresa, recorrência, situação e timestamps.
- Abrangências nacional, estadual, municipal e por empresa, com validação dos campos necessários e existência da empresa.
- Somente **FERIADO ativo**, na data e abrangência correspondentes, afeta a apuração. **DATA_COMEMORATIVA** é informativa.
- Recorrência anual repete dia/mês; feriados móveis exigem cadastro por ano. Um evento de 29/02 não é deslocado para outro dia em anos não bissextos.
- O efeito do feriado é calculado sem gravar um status manual na marcação. Desativar ou mudar o evento atualiza a próxima apuração aberta. A interface preserva separadamente o status editável.
- A regra de feriado existente foi mantida, assim como decisões manuais específicas e a interpretação de ocorrências. Competências fechadas continuam usando o resultado armazenado no fechamento.

## Arquivos alterados

| Arquivo | Motivo |
|---|---|
| `backend/app/database/models.py` | Admissão e entidade de evento. |
| `backend/app/database/migrations.py` | Migração aditiva para schema 7. |
| `backend/app/funcionarios/schemas.py` | Data opcional nos contratos da API. |
| `backend/app/calendario/__init__.py` | Novo módulo. |
| `backend/app/calendario/schemas.py` | Tipos e validação dos eventos. |
| `backend/app/calendario/routes.py` | Consulta, criação e edição/desativação. |
| `backend/app/calendario/service.py` | Elegibilidade, recorrência e abrangência. |
| `backend/app/apuracao/service.py` | Vínculo antes dos cálculos e integração dos feriados. |
| `backend/app/main.py` | Registro da rota do Calendário. |
| `backend/app/relatorios/routes.py` | Rótulo “Fora do vínculo” nas exportações. |
| `frontend/app.js` | Navegação global, admissão e integração dos efeitos calculados. |
| `frontend/js/calendario.js` | Lista, filtros e formulário de eventos. |
| `frontend/js/screens.js` | Correções do Resumo e exibição da admissão. |
| `frontend/js/components.js` | Badge no título e indicação dos efeitos na Conferência. |
| `frontend/styles.css` | Aviso, tabela, badges e layout do Calendário. |
| `frontend/index.html` | Carregamento do módulo e atualização de cache. |
| `backend/tests/test_admissao_calendario.py` | 21 testes do motor e migração. |
| `backend/tests/test_calendario_api.py` | 5 testes HTTP. |
| `backend/tests/test_tolerancia_intervalo.py` | Expectativa da versão atual do schema. |
| `frontend/tests/calendario-admissao.test.cjs` | 5 testes de integração do frontend. |
| `frontend/tests/calendario-browser.html` | Entrada restrita ao ambiente local de validação. |

## Banco/migrations

- Schema **7**: coluna nullable `funcionarios.data_admissao` e tabela `eventos_calendario`. Execução automática na inicialização da API, conforme o padrão existente.
- Não insere feriados automaticamente, não preenche admissões antigas e não reescreve snapshots de fechamento.
- A transição de schema 6 para 7 foi testada com preservação dos dados e repetição idempotente.
- O banco local já estava no schema 7 na inspeção final. Uma cópia foi criada via SQLite backup e submetida a duas execuções adicionais: hashes dos registros inalterados, `integrity_check = ok`, nenhuma violação de chave estrangeira. A validação da cópia abriu a origem somente para leitura.
- Código anterior preservado em `backups/revisao-admissao-calendario-antes.zip`.

## Testes

| Grupo | Existentes | Novos | Total | Passaram | Falharam |
|---|---:|---:|---:|---:|---:|
| Backend | 173 | 26 | 199 | 199 | 0 |
| Frontend | 15 | 5 | 20 | 20 | 0 |
| **Total** | **188** | **31** | **219** | **219** | **0** |

Execução completa: `python -m unittest discover -s backend/tests` e `node --test frontend/tests/*.test.cjs`. Sintaxe JavaScript também verificada.

Validação manual em navegador com banco fictício separado: cadastro/edição/desativação de evento, filtros por ano e tipo, recorrência, campo de admissão, aviso na Conferência, preservação da batida original e layout do Resumo. Sem erros JavaScript capturados nos fluxos inspecionados.

Evidências: `logs/testes-admissao-calendario-final.txt`, `logs/testes-admissao-calendario-frontend-final.txt` e `logs/migracao7-validacao.json`. Os testes de importação TXT, fechamento, ocorrências, tolerâncias e exportação existentes continuam passando.

## Problemas encontrados que ficaram fora do escopo

- Não foi identificado cálculo próprio de DSR no motor atual; esta etapa não introduz essa regra.
- O comportamento atual de feriado não calcula automaticamente trabalho/extra nesse status. Foi preservado, sem introduzir regras de remuneração de feriado.
- Persistem avisos de depreciação de `datetime.utcnow()` em código existente; não causaram falhas nos testes.
- Não foram alterados parsers TXT, fluxo de importação, arquitetura ou mecanismos de fechamento.
