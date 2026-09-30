# Confiabilidade operacional e políticas de horas

## Fase A — confiabilidade

Implementada somente em `workflow-navigation`, após o baseline de navegação `502ef16`.

- Apuração e relatórios GET não inicializam calendário, não fazem commit e não alteram status.
- Importação confirmada inicializa o calendário; `POST /competencias/{id}/inicializar-calendario` permite a ação explícita sem arquivo.
- `marcacoes[].problema`, `aguardando_conferencia` e `estado_conferencia` distinguem inconsistência bloqueante de revisão ainda não feita. `pendente` permanece como alias de trabalho restante para consumidores legados.
- `operacional` contém problemas, aguardando conferência, conferidos, total, dias sem registro, análises pendentes, conflitos de importação e arquivos.
- `fechamento.pode_fechar`, `motivo_bloqueio`, `motivos` e `proxima_acao` centralizam a decisão. `confirmar_pendencias` é aceito por compatibilidade, mas não remove bloqueios.
- POST/PATCH de marcação recusam confirmação de dia inválido. `POST /marcacoes/conferir-lote` confirma os válidos e informa IDs/motivos dos bloqueados.
- Schema SQLite 10: coluna aditiva `arquivos_recebidos.controle_importacao_json`, sem remoção de dados. Mantém registros importados, pendências e exclusões justificadas. Arquivos legados sem controle e sem marcações exigem análise.
- `POST /importadores/{id}/reanalisar` retoma o original. `POST /importadores/{id}/descartar-pendencias` exige justificativa, preservando arquivo e trilha. O descarte é decisão explícita de excluir um registro da apuração, não cadastro automático ou substituição de importação.
- Frontend mantém ausências como indisponíveis, respeita a decisão de fechamento e usa conferência em lote também para uma única linha. Problemas têm filtro próprio.

Validação: **263 testes Python e 62 testes JavaScript passaram**. Regressões novas em `test_confiabilidade_operacional.py` e `confiabilidade-operacional.test.cjs`. As fixtures antigas que dependiam de GET com efeito colateral agora inicializam o calendário explicitamente. Testes de fechamento excepcional foram convertidos em testes de recusa.

Falha preexistente: execução inicial de 257 testes apresentou um erro de limpeza SQLite no Windows. `_tem_unicidade_funcionario_data` retornava antes de consumir o cursor de índices. A materialização do resultado fecha o cursor antes do retorno; os testes de migração passaram após a correção. Nenhum teste foi ignorado.

Logs de execução locais (ignorados pelo Git): `logs/baseline-backend.txt`, `logs/phase-a-backend.txt`, `logs/phase-a-frontend.txt`.

Commit da Fase A: `3644914`. A suíte completa foi executada antes de iniciar a Fase B.

## Fase B — políticas por escala

### Arquitetura e compatibilidade

`banco_horas/regras.py` contém o contrato Pydantic e o cálculo puro, sem nomes de sindicatos, CNAEs ou seleção automática de instrumento coletivo. `Escala.politica_horas` recebe um objeto versionado; sua representação persistida é `politica_horas_json`.

O booleano `usa_banco_horas` **não foi removido**. Política nula mantém o cálculo legado, inclusive o prazo da empresa e a opção de feriados. Com política explícita, o booleano passa a refletir `percentual_banco > 0`. Atualizar outros campos não apaga a política; um cliente antigo não pode alterar apenas o booleano em contradição com ela. Enviar `politica_horas: null` é a opção explícita de voltar ao contrato anterior.

Uma escala pode usar `folha`, `banco` ou `misto`. Os percentuais devem somar exatamente 100; o modo também é validado. Adicionais são percentuais, sem cálculo monetário. Cada tipo de dia permite adicional específico ou herança do adicional geral.

Políticas explícitas usam a escala do vínculo histórico tanto na jornada quanto na distribuição. Datas anteriores ao primeiro registro do histórico usam a escala inicial, preservando a importação retroativa de funcionários sem data de admissão informada. Lacunas posteriores não recebem esse fallback. O cálculo de jornada legado permanece com a escala vigente, como antes; fechamentos existentes não são recalculados.

### Componentes, tipos de dia e arredondamento

- `extra_apurada_minutos`: HE bruta. No horário fixo com política explícita, conta minutos trabalhados fora dos intervalos previstos, após a tolerância de extra. Assim, 09h–12h/13h–19h numa jornada 08h–12h/13h–17h produz 120 minutos de HE e 60 minutos de atraso.
- `extra_folha_minutos`: parcela destinada à folha, antes de qualquer débito.
- `extra_banco_base_minutos`: complemento da HE distribuída; folha + base do banco = HE bruta.
- `extra_banco_minutos`: crédito depois do fator configurado.
- `debito_banco_minutos`: atrasos, se habilitados, mais folgas compensatórias; não reduz a base da divisão.
- `adicionais_folha`: minutos discriminados por adicional. Informação incompleta retorna `null`, sem apresentar subtotal como total.

No modo carga horária, permanece a apuração por duração diária, pois não existem intervalos fixos para inferir atraso por relógio. Déficits e extras de dias distintos continuam separados.

Feriado tem prioridade sobre sábado/domingo. Trabalho em feriado entra na distribuição da política explícita; no contrato legado, o comportamento anterior é preservado. `extra_minutos`/`extras_minutos` continuam excluindo a coluna separada de feriado; o novo `extra_apurada_minutos` inclui toda HE submetida à política, inclusive feriado.

Cada regra `normal`, `sabado`, `domingo`, `feriado` contém `fator_banco`, `base_fator` e adicional opcional. `base_fator` admite:

- `parcela_banco`: multiplica somente a parcela destinada ao banco;
- `extra_integral`: multiplica toda a HE apurada, mantendo a parcela da folha; esse resultado adicional é escolha explícita do operador;
- `decidir`: fator 1 aplica a distribuição simples; fator diferente de 1 com HE bloqueia o dia com `politica_requer_decisao`.

Exemplo de 120 minutos com 50/50 e fator 1,5: a base `parcela_banco` gera 60 para folha e 90 de crédito; `extra_integral` gera 60 para folha e 180 de crédito. Nenhuma opção foi adotada automaticamente como interpretação da CCT.

Precisão decimal, sem cálculos binários no motor. A folha usa arredondamento acumulado por funcionário/escala/política/competência, ordenado por data, com metade para cima. O banco recebe o complemento inteiro. O fator usa outro acumulador por tipo de dia sobre a base já distribuída. Quatro dias de 1 minuto, em 50/50, produzem 2 minutos na folha e 2 de base; fator 1,5 gera 3 de crédito. O snapshot diário registra valores exatos e efeito do fator/arredondamento. Acumuladores reiniciam a cada competência; não há transporte oculto de frações entre meses.

### Ledger, ciclos e fechamento

Ciclos contíguos são definidos por `ciclo_dias` e `inicio_ciclo`, obrigatórios se houver banco. O marco também determina ciclos anteriores por divisão inteira; não é uma data de início de vigência da política. O último dia do ciclo é inclusivo e é o vencimento do crédito. Duração 180 é configurável, sem preset jurídico.

Crédito e débito são lançamentos separados, mesmo com saldo líquido zero. O ledger mantém origem, funcionário, competência/versão, escala, datas, ciclo, vencimento, política aplicada, minutos, observação e estornos. A compensação continua FIFO, na razão 1:1, e só cruza lançamentos do mesmo ciclo. Lançamentos legados sem ciclo continuam se compensando entre si. Transporte entre ciclos e migração de saldo legado precisam de ajustes justificados.

`permite_saldo_negativo` controla a restrição por ciclo. A decisão central de fechamento inclui a projeção, sem persistir lançamentos; o fechamento revalida na mesma transação da geração/FIFO/snapshot. Folgas seguem a permissão do ciclo. Saldos opostos em ciclos distintos não liberam a desativação do banco.

O ajuste manual pode informar `lancamento_referencia_id` para herdar o ciclo, prazo e política de um lançamento ativo do mesmo funcionário. A referência fica persistida, e a data de referência precisa estar dentro do ciclo escolhido. Isso permite corrigir saldos antigos depois de mudar a política. Sem referência, o ajuste usa a política determinada pela escala/data. A data do lançamento registra o momento da operação.

Novo `snapshot_versao: 2`: política completa, componentes, arredondamento e saldos são congelados no fechamento, depois da geração e compensação. GET de competência fechada retorna esse snapshot integral. Ajustes posteriores aparecem no extrato atual; não reescrevem o fechamento. Reabertura continua estornando a versão anterior e permite novo fechamento com a configuração vigente. Snapshots anteriores permanecem intactos; sua complementação legada pelo ledger foi mantida por compatibilidade.

`fim_ciclo_credor`, `fim_ciclo_devedor`, `desligamento_credor`, `desligamento_devedor` e `adicional_saldo_percentual` descrevem o tratamento pretendido. `tratamentos_pendentes` informa minutos, natureza, ciclo e lançamentos de origem. Pagamento, transporte, desconto e dispensa são **indicações para confirmação**, sem baixa automática nem valores em reais. O extrato mostra esses avisos; resumo e exportação preservam os avisos existentes no momento do fechamento.

### Migração SQLite 11

Migração transacional, aditiva e idempotente:

| Tabela | Colunas adicionadas |
| --- | --- |
| `escalas` | `politica_horas_json TEXT NULL` |
| `lancamentos_banco_horas` | `politica_aplicada_json TEXT NULL`, `ciclo_inicio DATE NULL`, `ciclo_fim DATE NULL`, `lancamento_referencia_id INTEGER NULL` com FK para o próprio ledger |

Não preenche políticas, não aplica CCT, não reescreve lançamentos ou snapshots. A versão 10 da Fase A adiciona o controle de importação, como descrito acima. O banco real não foi aberto nem migrado nesta tarefa: as validações usaram bancos temporários.

### Endpoints da Fase B

| Endpoint | Alteração |
| --- | --- |
| `POST /escalas`, `PUT/PATCH /escalas/{id}`, `GET /escalas` e `GET /escalas/{id}` | Política configurável, validação e compatibilidade com booleano |
| `PATCH /empresas/{id}` | Prazo legado só é obrigatório se alguma escala ainda usar o contrato legado |
| `GET /apuracao` | Componentes, políticas aplicadas, auditoria de arredondamento, ciclos e bloqueios projetados |
| `POST /competencias/{id}/fechar` | Geração separada de crédito/débito e snapshot v2 imutável |
| `POST /competencias/{id}/reabrir` | Mantém estorno/reconciliação por versão, agora com ciclos |
| `POST /banco-horas/ajustes` | Política/ciclo por data ou referência explícita a lançamento anterior |
| `GET /banco-horas/extrato` | Ciclos, política aplicada, referência do ajuste e tratamentos pendentes |
| `POST/PATCH /ocorrencias` | Folgas respeitam cobertura e saldo negativo por ciclo |
| `GET /relatorios/excel`, `/relatorios/impressao`, `/relatorios/espelho-ponto`, `/relatorios/espelho-ponto-lote` | Distribuição, adicionais, saldos e compensações; Excel inclui políticas aplicadas e tratamentos pendentes quando existentes |

Novos estados de consulta: `pendencia_tipo=politica_requer_decisao`, `bloqueios_politica` e `fechamento.proxima_acao=revisar_banco`. A UI permite configurar a política em Escalas, consultar distribuição no Resumo e escolher o ciclo do ajuste no Banco de horas. As abas legadas do Excel permanecem no formato anterior.

### Validação da Fase B

Resultado final: **281 testes Python aprovados (39,827 s), 64 testes JavaScript aprovados**, sem skips. `compileall`, verificação de sintaxe JavaScript e `git diff --check` também concluídos. A suíte completa foi repetida após a inclusão do ajuste por referência de ciclo.

`backend/tests/test_politicas_horas.py` cobre 100% folha, 100% banco, 50/50, atraso separado, crédito/débito/FIFO, snapshot e mudança futura, quatro tipos de dia e duas bases do fator, ambiguidade, arredondamento, validações, saldo negativo, ciclos distintos, vencimento e desligamento, migração idempotente, relatórios, leitura sem persistência, folgas e ajustes referenciados.

`frontend/tests/politicas-horas.test.cjs` verifica serialização do formulário, modos, preservação da escolha pendente, distribuição e dados ausentes. Testes de CTA e formulário anteriores foram ampliados. O teste antigo que esperava saldo fechado variar após ajuste foi atualizado: o snapshot permanece, enquanto o extrato mostra o saldo atual.

Verificação no navegador: edição da escala salva pela API, alteração de 50/50 para 60/40 preserva a competência fechada em 50/50; resumo fictício com 4h brutas, 2h para folha, 2h30 de crédito com fator e 1h de débito. Nenhum dado real introduzido.

Logs locais: `logs/phase-b-backend.txt`, `logs/phase-b-frontend.txt`, `logs/phase-b-policies.txt` (ignorados pelo Git). A prévia em `logs/preview_policies.py` usa SQLite e uploads temporários, somente a partir deste worktree.

### Decisões humanas ainda necessárias

1. Confirmar a base do fator 1,5 na combinação com 50/50. O sistema aceita ambas as composições explicitamente; não afirma qual interpretação jurídica é correta.
2. Definir adicional geral e eventuais adicionais por dia, marco do ciclo, débitos admitidos e condições de saldo negativo.
3. Confirmar tratamento/adicional do crédito no fim do ciclo, destino de débitos e regras concretas de desligamento. O sistema sinaliza os saldos e mantém o ledger até ajuste documentado.
4. Validar esses parâmetros contra o instrumento completo e os aditivos aplicáveis. O anexo forneceu o requisito funcional e um nome de PDF truncado, não o texto integral. O [portal oficial do SETCESP](https://conteudo.setcesp.org.br/cct26-27) foi consultado para identificar a referência; não foi usado para presumir cláusulas não disponibilizadas.

Sem implementação dos itens excluídos do pedido: fila multiempresa, cadastro automático por TXT, substituição avançada de importação, valores monetários ou seleção automática de CCT.

## Arquivos alterados

Caminhos relativos à raiz deste worktree. O baseline anterior de navegação está separado em `502ef16`.

### Fase A — commit 3644914

- `RELATORIO-CONFIABILIDADE-E-POLITICAS.md`
- `backend/README.md`
- `backend/app/apuracao/operacional.py`
- `backend/app/apuracao/routes.py`
- `backend/app/apuracao/service.py`
- `backend/app/arquivos/schemas.py`
- `backend/app/competencias/routes.py`
- `backend/app/competencias/service.py`
- `backend/app/database/migrations.py`
- `backend/app/database/models.py`
- `backend/app/importadores/routes.py`
- `backend/app/importadores/schemas.py`
- `backend/app/marcacoes/routes.py`
- `backend/app/relatorios/routes.py`
- `backend/tests/test_admissao_calendario.py`
- `backend/tests/test_apuracao_resumo.py`
- `backend/tests/test_banco_horas.py`
- `backend/tests/test_cadastros_api.py`
- `backend/tests/test_calendario_api.py`
- `backend/tests/test_confiabilidade_operacional.py`
- `backend/tests/test_espelho_ponto.py`
- `backend/tests/test_fechamento_competencia.py`
- `backend/tests/test_importacao_txt_flow.py`
- `backend/tests/test_integridade_correcao.py`
- `backend/tests/test_migrations.py`
- `backend/tests/test_ocorrencias.py`
- `backend/tests/test_support.py`
- `frontend/app.js`
- `frontend/js/screens.js`
- `frontend/tests/confiabilidade-operacional.test.cjs`
- `frontend/tests/demissao-feriado.test.cjs`

### Fase B — política genérica e rastreabilidade

- `RELATORIO-CONFIABILIDADE-E-POLITICAS.md`
- `backend/README.md`
- `backend/app/apuracao/service.py`
- `backend/app/banco_horas/folgas.py`
- `backend/app/banco_horas/regras.py`
- `backend/app/banco_horas/schemas.py`
- `backend/app/banco_horas/service.py`
- `backend/app/competencias/routes.py`
- `backend/app/database/migrations.py`
- `backend/app/database/models.py`
- `backend/app/empresas/routes.py`
- `backend/app/escalas/routes.py`
- `backend/app/escalas/schemas.py`
- `backend/app/funcionarios/historico_escalas.py`
- `backend/app/relatorios/routes.py`
- `backend/tests/test_banco_horas.py`
- `backend/tests/test_politicas_horas.py`
- `frontend/app.js`
- `frontend/index.html`
- `frontend/js/banco-horas.js`
- `frontend/js/screens.js`
- `frontend/tests/confiabilidade-operacional.test.cjs`
- `frontend/tests/espelho-lote.test.cjs`
- `frontend/tests/politicas-horas.test.cjs`
