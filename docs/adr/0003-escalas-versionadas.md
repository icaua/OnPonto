# ADR 0003 — Configuração de escala por vigência

Status: adotado no pacote 02.

A identidade de Escala e o histórico de vínculo do funcionário continuam separados das versões de configuração. O resolvedor carrega as versões em lote e escolhe a regra pela data do dia, inclusive no banco de horas. O cadastro corrente é um espelho da última configuração para manter o formulário/API existentes; não é a fonte de regras históricas.

A migração 14 captura a configuração legada com início desconhecido, identificado por `legado_vigencia_desconhecida`. Não há como reconstruir alterações anteriores: essa limitação fica explícita. Snapshots fechados não são recalculados. Uma alteração cria configuração imutável, com início informado ou próxima data futura disponível (amanhã, ou depois da última versão agendada). Apenas o fim de validade da versão anterior é ajustado. Triggers SQLite impedem alteração de configuração, exclusão e sobreposição; a migração verifica FK e integridade dentro da transação.

`jornadas_semana` usa chaves 0 (segunda) a 6 (domingo), minutos e horários próprios opcionais. Em horário fixo, jornada positiva exige horários coerentes com os minutos. Domingo sem trabalho e feriado mantêm precedência; sábado compensado mantém o tratamento legado. O formulário informa a vigência; configuração detalhada por dia está disponível no contrato da API e será ampliada no pacote 04.

Vigência que alcança fechamento existente é recusada. Mudanças que atingem marcações abertas preservam evidência e horários, retiram a confirmação e registram necessidade de revisão. Ausência de uma versão válida produz pendência, sem fallback para configuração futura.

Rollback de código após uso da migração exige restaurar conjunto SQLite + uploads compatível em ambiente isolado: código antigo ignoraria versões. Não executar downgrade nem restauração sobre os dados do usuário. A migração é aditiva e não foi executada no banco real.
