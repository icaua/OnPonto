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
| 00 | validado | commit identificado no próximo checkpoint | backend 350/350; Node 95/95; compileall/diff OK; Playwright OK nas duas resoluções | nenhuma | `docs/benchmarks/00-baseline.json`, 3 portes completos | nenhum |
| 01 | não iniciado | — | — | — | — | depende de 00 |
| 02 | não iniciado | — | — | — | — | depende de 01 |
| 03 | não iniciado | — | — | — | — | depende de 02 |
| 04 | não iniciado | — | — | — | — | depende de 01–03 |
| 05 | não iniciado | — | — | — | — | depende de 01–04 |
| 06 | não iniciado | — | — | — | — | depende de 01–05 |
| 07 | não iniciado | — | — | — | — | depende de 04–06 |
| 08 | não iniciado | — | — | — | — | depende de 00–07 |
| 09 | não iniciado | — | — | — | — | depende da integração estabilizada |

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
