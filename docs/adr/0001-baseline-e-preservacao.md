# ADR 0001 — baseline e preservação durante a modernização

Estado: aceito para o pacote 00. Data: 10/10/2026.

## Contexto

A auditoria usou `038a3c5`; main local avançou até `65d5059`. Os seis commits adicionais já oferecem resolvedor de vínculos, backup do SQLite e tratamento explícito da API indisponível. O cálculo ainda está acoplado à orquestração e o fechamento mantém apenas um snapshot corrente.

## Decisão

Usar a main local mais recente em branch de integração, com commits separados por pacote e gates de teste. Nenhum banco instalado é aberto pelos novos harnesses. Fixtures construídas via ORM, testes HTTP em loopback e golden master estruturado caracterizam o comportamento existente, inclusive suas limitações.

Manter o resolvedor em memória já existente. Não ativar WAL nem trocar banco/runtime. Não mudar regra de intervalo, fechamento ou percentual neste checkpoint. O backup completo é introduzido como primitiva offline, com hashes e restauração sem sobrescrita, antes de sua integração operacional no pacote 08.

## Consequências e limites

Golden masters não certificam regras trabalhistas: capturam o resultado atual para detectar divergências. Correções posteriores precisam de expectativas explícitas e justificativa. Tracemalloc mede alocações Python e torna o benchmark mais lento; a comparação usará o mesmo harness/cenário/runtime. Um único benchmark de mutação não estima percentis de produção.

Os relatórios `RELATORIO-OCORRENCIAS-AFASTAMENTOS.md` e `RELATORIO-RESUMO-ADMISSAO-CALENDARIO.md` confirmam ausência de DSR. O plano pede homologação dessa regra no pacote 04 sem fornecer fórmula. Foi solicitada definição ou ajuste explícito de escopo ao usuário; não será inventado cálculo.

Rollback de código por reversão dos commits. Não restaurar binários de SQLite por checkout Git. Não substituir automaticamente dados instalados por uma fixture ou conjunto restaurado.
