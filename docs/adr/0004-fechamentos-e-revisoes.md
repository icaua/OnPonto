# ADR 0004 — Fechamentos preservados e revisão otimista

Status: adotado no pacote 03.

Migração aditiva 15 cria `fechamentos_versoes` e `reaberturas_fechamento`, ambas append-only com triggers contra UPDATE/DELETE. Cada fechamento guarda exatamente o JSON corrente, número, identificadores das regras e origem. Snapshot legado é copiado sem reserializar e sem duplicar na próxima inicialização; regras antigas não identificáveis permanecem sem identidade inventada. Fechamento legado sem snapshot registra explicitamente essa ausência. Divergência entre snapshot ativo e versão preservada interrompe a migração.

Reabertura guarda evento, estorna ledger e libera apenas o ponteiro corrente, em uma transação; a versão anterior continua disponível por GET `/competencias/{id}/fechamentos`. Novo fechamento cria a versão seguinte. Referências do ledger continuam sendo competencia_origem_id + versao_fechamento. Falha em qualquer parte reverte o conjunto.

`MarcacaoPonto.revisao` é controlada pelo mapper SQLAlchemy: UPDATE compara revisão anterior e incrementa. Além disso, clientes HTTP devem enviar a revisão que leram em PATCH, upsert POST, decisões de batidas e mapa de revisões em conferir-lote; ausência ou divergência retorna 409. DELETE de decisão usa query `revisao`. Chamadas Python internas mantêm assinatura compatível, mas continuam sujeitas ao controle ORM; não são contrato de edição externa.

Operações mutáveis usam lock SQLite antes de validar e rollback inclusive em erros de validação. O lock coordena fechamento/importação; o token detecta a janela desatualizada. Confirmação de importação não faz mais commit intermediário da reanálise. Upload preserva original em uma unidade própria, revalida fechamento antes da análise e conserva evidência de análise recusada.

Autosave mantém edição durante 409, suspende reenvio e compara valores atuais com a edição em diálogo. Usar valores do servidor ou reaplicar após revisão exige escolha explícita. Resposta de salvamento atualiza o token do próximo envio sem sobrescrever edição em voo. Respostas de apuração não substituem dias em fila ou ativos.

O golden exclui somente o novo metadado de transporte `revisao`; resultados trabalhistas, snapshots esperados e Excel não foram alterados/regenerados. Helpers dos testes HTTP sequenciais passam a ler/enviar o token; testes concorrentes enviam deliberadamente o mesmo token sem esses helpers. Benchmark lê tokens antes das operações medidas, mantendo a medição do handler comparável.

Rollback de código exige ambiente/dados compatíveis conforme ADR 0003. Não executar código antigo sobre DB versionado nem apagar novas tabelas. Validação usa apenas conjuntos fictícios. Nenhum teste substitui homologação de CCT.
