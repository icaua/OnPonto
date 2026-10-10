# 0008 — Módulos e conferência por funcionário

Data: 2026-10-10. Estado: aceito.

O controlador vanilla e as telas foram separados gradualmente em módulos exportados UMD/CommonJS: API, navegação, store, conferência, importação, escalas e relatórios, com quatro módulos de telas. Os wrappers existentes preservam contratos, URLs e os testes legados; testes novos importam as interfaces diretamente. Não houve mudança de CSS ou framework.

Conferência carrega triagem e um pacote de dias por funcionário. `/apuracao/dias` acrescenta `registros` com horários editáveis, originais, auditoria e revisão, na mesma leitura SQLite dos resultados oficiais. Cache distingue resumo de triagem e detalhes; sequências e revisão impedem respostas antigas de substituir edições mais recentes. Troca de pessoa/contexto aguarda flush confirmado e recusa nova edição ainda pendente. Conflito 409 exige decisão humana. Sem autosave, navegação externa também preserva alterações não salvas.

Resultados locais de trabalho/saldo online ficam indisponíveis até a API responder. Mensagens locais não afirmam persistência; reabertura do dia aguarda PATCH. A grade reutiliza nós existentes durante atualização rotineira, preservando foco/rolagem. Demonstração continua explícita; leitura OCR simulada não pode entrar em dados reais. Nenhum OCR foi implementado.

Validação: testes JS de módulos/filas/revisões/rotas e navegador com DB fictício nas duas resoluções, ciclo completo, duas janelas, foco e rolagem. Golden backend preservado. Rollback: reverter frontend e o campo aditivo do endpoint; não há migração de schema ou alteração histórica.
