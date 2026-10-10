# 0005 — Intervalos explícitos e DSR em dias

Status: implementado no pacote 04. Política de DSR recebida diretamente do usuário em 10/10/2026.

Escalas antigas mantêm campos nulos e o motor anterior. Intervalo fixo, flexível ou sem intervalo e registro por batidas/pré-assinalação são escolhas explícitas, capturadas na versão da regra. Jornadas próprias usam seus horários, validam a duração e herdam apenas a política de intervalo; sábado de quatro horas sem almoço pode declarar sua própria política. Nenhuma duração ou horário calculado é gravado nas batidas originais.

Pré-assinalação aplica exclusivamente o par previsto completo, dentro da entrada/saída reais, quando ambas as batidas de intervalo estão ausentes. Registro parcial fica pendente; quatro batidas reais prevalecem. API e relatórios distinguem origem real, corrigida e pré-assinalada. Flexível considera duração efetiva, sem criar HE pelo simples deslocamento de um intervalo de duração igual. Déficit e excesso de intervalo não são somados duas vezes. Destinação percentual das HE, adicional da folha e fator de banco permanecem separados.

DSR v1: descanso configurável, domingo por padrão; referência nos seis dias imediatamente anteriores ao descanso. Uma ou várias faltas injustificadas perdem um descanso; atestados, abonos, atrasos e faltas justificadas não causam perda. Feriados desse período também perdem um dia cada, conforme política explícita da escala. Descanso coincidente com feriado é uma única data. Resultado em dias, sem conversão salarial ou em minutos. Falta justificada exige motivo documentado.

Feriado usa o descanso que encerra seu período de referência. Isso pode exigir dias do mês seguinte. Referência sem marcação, sem conferência ou com problema produz `desconto_dias=null` e bloqueia fechamento. Não se fabricam dias futuros nem desconto zero. Mudança do dia de descanso dentro de uma referência exige revisão, pois a política de transição não foi definida. Versões antigas e snapshots fechados não recebem DSR retroativamente.

Migração 16 é aditiva: campos de escala e dependências imutáveis de fechamento. O snapshot guarda regra, política, datas, IDs e revisões de referência. Edição de uma marcação utilizada em DSR fechado, ocorrência, calendário, vínculo ou regra que a afete exige reabertura explícita. Reabertura preserva versões anteriores; deixa de bloquear apenas as referências do fechamento desativado. FK impede remoção de marcação historicamente referenciada.

Excel/espelho preservam horários reais vazios na pré-assinalação e acrescentam informação prevista separada. Legenda de feriado passa de “Horas 100% (feriado)” a “Horas em feriado”: o percentual depende da regra. Golden master não foi regenerado; comparação normaliza exclusivamente esses dois cabeçalhos, sem alterar valores, snapshots ou ledger. Testes específicos verificam adicional de 60% e destinação 50/50 sem legenda falsa de 100%.

Rollback: código antigo não entende os novos contratos; restaurar backup anterior em destino isolado, mantendo SQLite e uploads juntos. Não fazer downgrade ou reverter migração sobre dados reais. A migração foi exercitada apenas em bancos fictícios; recuperação operacional continua prevista no pacote 08.
