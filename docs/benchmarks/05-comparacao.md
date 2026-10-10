# Pacote 05 — comparação com baseline

Mesmo cenário fictício v1, runtime e tracing. GET usa a mediana de três amostras; mutações têm uma amostra. Números incluem transferência HTTP. Consultas incluem escritas/transaction statements. Não são percentis ou RSS.

| Pessoas | Operação | SQL 00 → 05 | Latência 00 → 05 (ms) | Redução de latência |
|---:|---|---:|---:|---:|
| 50 | GET /apuracao | 340 → 12 | 834 → 726 | 13.0% |
| 50 | PATCH marcação | 355 → 80 | 1397 → 879 | 37.1% |
| 50 | fechar | 720 → 136 | 1890 → 1129 | 40.3% |
| 50 | exportar Excel | 1 → 1 | 2332 → 2145 | 8.0% |
| 50 | reabrir | 479 → 55 | 941 → 234 | 75.1% |
| 250 | GET /apuracao | 1670 → 12 | 4429 → 3590 | 18.9% |
| 250 | PATCH marcação | 1685 → 280 | 7599 → 4016 | 47.1% |
| 250 | fechar | 3514 → 535 | 9503 → 5697 | 40.1% |
| 250 | exportar Excel | 1 → 1 | 16403 → 9885 | 39.7% |
| 250 | reabrir | 2341 → 188 | 5439 → 1231 | 77.4% |
| 1000 | GET /apuracao | 6670 → 12 | 19621 → 14443 | 26.4% |
| 1000 | PATCH marcação | 6685 → 1030 | 31744 → 16259 | 48.8% |
| 1000 | fechar | 14014 → 2035 | 41169 → 22615 | 45.1% |
| 1000 | exportar Excel | 1 → 1 | 159886 → 39816 | 75.1% |
| 1000 | reabrir | 9341 → 688 | 20745 → 5179 | 75.0% |

Primeiro PATCH cria cache para o mês; o PATCH subsequente medido separadamente usa 30 comandos SQL em todos os portes. A triagem aquecida usa 11 consultas; um funcionário usa 11 consultas e retorna 38.093 bytes nos três portes.

Em 1.000 pessoas o resumo reduz resposta de 51.541.403 para 1.030.749 bytes (98,0%). Ele preserva totais oficiais e ainda calcula o mês; triagem oferece contadores sem prometer aprovação financeira. A conferência integral legada continua disponível e será substituída no frontend gradualmente.

O Excel passou de 160 s para 40 s com o mesmo conteúdo/formatos, após retirar max_row dos laços. Sua memória continua proporcional ao número de células; não houve mudança para streaming. O hash do backend em 05-final.json verifica implementação estável entre cenários. Registro intermediário 05-triagem-lotes.json permanece para auditoria da otimização.
