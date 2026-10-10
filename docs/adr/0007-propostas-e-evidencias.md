# 0007 — Prévia preservada e evidência imutável

Pacote 06, 10/10/2026. A confirmação usava reinterpretação e consultas por dia. Agora o pipeline mantém armazenamento, parsers e proposta separados; o endpoint coordena a transação. Prévia append-only guarda SHA-256, versão do adaptador, contexto de cadastro/escala/ignorados e revisão. HTTP exige `revisao_previa`; alterações de contexto, conteúdo ou adaptador exigem reanálise explícita. GET `/importadores/{id}/previa` recupera a proposta. Não se confirmam sugestões automaticamente.

Confirmação identifica a seleção pelo hash da prévia e IDs únicos ordenados. Reenvio retorna a resposta registrada com `idempotente=true`, sem nova escrita; uma seleção diferente processa apenas os registros ainda não resolvidos. Marcações por competência e pessoas são buscadas em lote. Placeholder automático intocado pode receber importação; decisão humana ou marcação existente prevalece. Upload igual na mesma competência reutiliza o original somente após verificar o hash do arquivo existente. Nome de novo recebimento fica na auditoria. Arquivo ausente/adulterado nunca é sobrescrito.

Schema 18 adiciona prévias, confirmações, documentos, N eventos brutos e auditoria. Triggers impedem UPDATE/DELETE históricos. Evento bruto admite apenas ligação inicial a uma marcação; horário, índice e fonte não mudam. Fonte independe da pessoa posteriormente associada. Batidas duplicadas são mantidas. TXT log e ID/Tempo guardam também ordem e linha física; XLSX registra aba/linha/coluna; quando o legado não conhece linha/página, essa informação permanece desconhecida. A interpretação diária e os JSONs de compatibilidade são preservados. Decisões de descarte/restauração permanecem no histórico append-only e no histórico legível já usado pelo frontend.

Backfill é SQL idempotente, sem abrir arquivos da instalação. Copia valores e históricos legados sem apagar JSONs; hash histórico desconhecido permanece NULL. Nova observação do arquivo cria metadado com origem explícita. Anexos sucessivos ficam preservados, com hash e documento próprio. Inventário somente leitura detecta ausentes, divergência, referência inválida e órfão, sem exclusão automática:

```powershell
cd backend
python -m app.evidencias.inventario --banco CAMINHO_COPIA_DB --uploads CAMINHO_COPIA_UPLOADS --backend CAMINHO_COPIA_BACKEND
```

XLSX tem limites de contêiner antes do openpyxl: 100 MiB expandidos, 4096 entradas, 20 MiB por entrada, razão 200 acima de 1 MiB, sem traversal ou criptografia. Nenhum arquivo é extraído. Hardening geral continua no pacote 09.

Rollback de código não implica remover schema/evidência. Restaurar o conjunto íntegro em destino novo quando necessário, com escritores parados. Não fazer downgrade destrutivo; preservar dados novos. Nenhum DB real foi migrado.
