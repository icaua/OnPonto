# Banco de horas por escala — relatório de implementação

Data: 22/09/2026. Implementação da proposta revisada e do adendo de histórico de escala, concluída em seis partes sequenciais.

## Resultado

O banco de horas tem registros próprios de créditos, débitos e compensações. O fechamento gera lançamentos por dia a partir da mesma apuração usada no snapshot. O saldo atravessa competências e é apresentado separadamente dos totais de ponto. Escalas sem banco continuam com o fluxo anterior.

- Ativação individual por escala; prazo positivo e política de feriado configurados na empresa.
- Lançamentos com origem, datas de referência/entrada/vencimento, escala, política aplicada, versão e informações de estorno. Minutos sempre positivos; natureza determina o sinal.
- Compensações explícitas entre crédito e débito; saldo e consumo derivados, sem coluna de saldo ou de minutos consumidos.
- Crédito novo cobre os débitos mais antigos. Débito novo usa créditos por vencimento, data de referência e identificador. A reconstrução reproduz deterministicamente a ordem de entrada no ledger.
- Fechamento, versão, snapshot, lançamentos e compensações na mesma transação; repetição e concorrência protegidas no backend.
- Reabertura estorna a geração da versão invalidada, preserva o histórico e reconstrói as compensações dos funcionários afetados. Novo fechamento gera outra versão.
- Histórico de vínculo de escala consultado por dia; bloqueio de desativação do banco quando qualquer funcionário atualmente vinculado possui saldo individual diferente de zero.
- Folga compensatória integral/parcial reaproveita a interpretação de ocorrências, com débito explícito e sem falta ou atraso artificial.
- Ajustes manuais de crédito/débito exigem motivo. Correção de ajuste por estorno; lançamento automático é corrigido pela reabertura da competência.
- Tela Banco de horas com saldos, extrato, corte por data, compensações, estornos e alertas. Resumo mensal, espelhos, impressão e Excel apresentam o banco em bloco próprio, incluindo saldo no desligamento.

## Como usar

1. Reinicie o backend atualizado e recarregue o frontend. A inicialização aplica a migração de schema 9.
2. Na edição da empresa, informe o prazo de compensação em dias e escolha se as horas trabalhadas em feriados entram no banco.
3. Na edição da escala, habilite o banco de horas. O prazo da empresa precisa estar configurado antes dessa ativação.
4. Confira normalmente o ponto. O fechamento publica os lançamentos diários; uma competência aberta ainda não publica suas extras/atrasos no banco.
5. Consulte **Banco de horas** no menu da empresa. Para saldo inicial ou correção autorizada, use **Registrar ajuste**, indicando natureza, minutos, data de referência e motivo.
6. Para consumo de saldo em ausência autorizada, cadastre a ocorrência **Folga compensatória** integral ou parcial. Para corrigir apuração já fechada, reabra a competência e depois feche novamente.

Créditos vencidos continuam disponíveis. Os alertas preventivos usam 30 dias na interface; a API aceita o parâmetro `dias` entre 0 e 365. O vencimento não paga, desconta, zera nem exclui horas automaticamente.

## Decisões de validação

- Folga com saldo insuficiente recebe erro 409 com os minutos necessários/disponíveis. Outras folgas em competências abertas reservam saldo para evitar promessas duplicadas. O fechamento revalida a cobertura efetiva depois do FIFO e é revertido integralmente se faltar saldo.
- Um estorno posterior pode deixar uma folga anteriormente coberta sem crédito correspondente. A ocorrência e o débito permanecem auditáveis; a tela apresenta um alerta específico para revisão pelo operador.
- Dias com pendência de cálculo em escala com banco bloqueiam o fechamento, inclusive excepcional, para não consolidar valores indefinidos. O fechamento excepcional das escalas sem banco mantém o comportamento anterior.
- Não é possível remover o prazo da empresa enquanto houver escala com banco habilitado. A alteração da política e a ativação da escala são serializadas com as demais escritas SQLite.
- Desativação verifica cada funcionário da escala. Um saldo positivo e outro negativo não se anulam para liberar a desativação.
- Ajustes manuais não aceitam referência futura. Créditos precisam de prazo; débito manual pode ser registrado sem prazo.
- Funcionários com histórico no ledger não podem ser transferidos entre empresas. Escalas com histórico são preservadas quando excluídas, por desativação cadastral.

## Limitações do histórico e das consultas

**Trocas anteriores à migração não podem ser reconstruídas.** A migração cria um vínculo inicial com a escala atual e a data mais antiga disponível entre cadastro, admissão e marcações existentes. Isso não comprova qual escala realmente valia antes da implantação. Não são inventados vínculos com escalas antigas nem lançamentos de banco para competências já fechadas.

**O motor diário de ponto continua usando a escala atual do funcionário.** Em uma competência aberta, trocar a escala ainda pode alterar jornada, atraso e extra recalculados de dias anteriores. O histórico foi aplicado à elegibilidade e à escala de origem do lançamento do banco, conforme o adendo; não foi aplicado ao cálculo diário do ponto. Esse comportamento precisa ser considerado ao conferir um mês com mudança de escala.

As trocas registradas pela rota de funcionários passam a fechar o vínculo anterior e abrir o novo na data local da alteração. Como os limites são inclusivos, no dia da troca vence o vínculo com início mais recente; em empate, o último registro. Não foi criada edição retroativa desse histórico.

O corte de saldo usa a **data de referência** dos lançamentos atualmente ativos. Ele mostra o saldo histórico corrigido, não uma fotografia do que o operador conhecia no passado. Estornos posteriores alteram essa consulta. O snapshot do ponto fechado permanece preservado; o bloco do banco é consultado separadamente no ledger atual.

O resumo de competência aberta mostra somente lançamentos já oficiais, incluindo ajustes com referência no mês. Ele não antecipa o saldo que será gerado pelo fechamento. Fechamentos legados com versão zero não recebem bloco de banco retroativamente. Se o operador reabrir e fechar uma competência antiga após habilitar o recurso, esse novo fechamento segue a regra atual.

## Migração e preservação

- Schema SQLite: **9**. Novas tabelas `historico_vinculo_escala`, `lancamentos_banco_horas` e `compensacoes_banco_horas`; novas configurações e versão do fechamento.
- Migração incremental e idempotente, com checagem de chaves estrangeiras e preservação dos snapshots existentes.
- Banco desabilitado por padrão nas escalas; prazo inicialmente não configurado; feriado fora do banco por padrão.
- A implementação e as validações desta rodada usaram bancos temporários. O banco real não foi migrado manualmente nem recebeu lançamentos de teste.
- Backup dos fontes anteriores à rodada: `logs/fontes-antes-banco-horas-20260922-195132.zip`. Esse arquivo não contém backup dos dados reais. A rotina de cópia do banco e dos uploads antes de atualizar permanece descrita no README.

## API

| Método e rota | Finalidade |
| --- | --- |
| `GET /banco-horas/saldo?funcionario_id=&data_limite=` | Saldo centralizado, com corte opcional por referência |
| `GET /banco-horas/extrato?funcionario_id=&data_limite=` | Lançamentos, consumo, saldo restante/acumulado, compensações e estornos |
| `GET /banco-horas/resumo?empresa_id=` | Saldos dos participantes e saldo no desligamento |
| `GET /banco-horas/alertas?empresa_id=&dias=30` | Créditos vencidos, próximos do vencimento e folgas sem cobertura |
| `POST /banco-horas/ajustes` | Ajuste com `funcionario_id`, `natureza`, `minutos`, `data_referencia` e `observacao` |
| `POST /banco-horas/lancamentos/{id}/estornar` | Estorno de ajuste manual com `motivo` obrigatório |

Fechamento e reabertura continuam nas rotas existentes de competências. As configurações foram acrescentadas às rotas existentes de empresas e escalas. A ocorrência usa as rotas existentes de ocorrências com o tipo `FOLGA_COMPENSATORIA`.

## Validação

Cada etapa executou a suíte completa do backend antes do avanço:

| Etapa | Testes aprovados | Evidência |
| --- | ---: | --- |
| 1 — Fundação | 230 | `logs/testes-banco-horas-parte1.txt` |
| 2 — Geração diária | 236 | `logs/testes-banco-horas-parte2.txt` |
| 3 — FIFO e saldo | 243 | `logs/testes-banco-horas-parte3.txt` |
| 4 — Reabertura | 246 | `logs/testes-banco-horas-parte4.txt` |
| 5 — Folga compensatória | 252 | `logs/testes-banco-horas-parte5.txt` |
| 6 — Consultas e interface | 256 | `logs/testes-banco-horas-parte6.txt` |
| Revisão final do backend | 257 | `logs/testes-banco-horas-final.txt` |
| Frontend | 40 | `logs/testes-banco-horas-frontend-final.txt` |

Os testes novos cobrem migração repetida, vínculo histórico, integridade dos lançamentos, política congelada, feriados, neutralidade sem banco, concorrência de fechamento/configuração, rollback, FIFO, cortes de saldo, estorno/reabertura, bloqueio de desativação, reserva/consumo de folgas, rescisão, espelho e preservação do snapshot. Os testes de frontend cobrem exibição, escape de conteúdo, consulta por data, ajustes e modo offline.

Validação no navegador com API real e dados fictícios isolados: consulta de saldos/alertas/extrato, registro de ajuste manual de 30 minutos, atualização do saldo de +08:00 para +08:30 e bloco separado no resumo mensal, incluindo saldo de desligamento. O roteiro local está em `logs/preview_banco_horas.py` e usa uma base temporária, sem acessar o banco real.

Permanecem fora do escopo cálculos em reais, pagamento/desconto, folha, integração contábil automática e decisões jurídicas sobre compensação ou vencimento.
