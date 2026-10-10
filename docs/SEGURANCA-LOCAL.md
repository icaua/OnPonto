# Operação local e privacidade

Abra pelo iniciar_onponto.bat / iniciar_onponto.sh, mantendo API em 127.0.0.1 e frontend HTTP na porta 5500. A sessão é iniciada automaticamente; não há cadastro de login. File://, Origin null e origens não cadastradas serão recusados. Para outra porta local, defina ONPONTO_FRONTEND_ORIGINS com a origem exata (por exemplo http://127.0.0.1:5501), antes de iniciar a API. Nunca use origem genérica `*`. Use um processo/worker.

Integrações locais precisam GET /sessao/local, guardar o cookie e enviar X-OnPonto-CSRF recebido no JSON em POST/PUT/PATCH/DELETE. Não colocar token em URL ou logs. Sessões duram oito horas e desaparecem ao reiniciar; o frontend renova automaticamente em 401. A raiz mantém o healthcheck do instalador. A proteção se dirige a acesso indevido por navegador; processos com acesso à conta/pasta continuam sujeitos às permissões do sistema operacional.

Arquivos: 25 MiB; requisição 26 MiB. Texto UTF-8/UTF-16 e codificações existentes, XLSX limitado antes de abrir, PNG/JPEG até 40 milhões de pixels e PDF até 512 páginas com streams limitados. PDF criptografado, ativo ou com filtros sem validação suportada é recusado. O original aceito não é normalizado ou sobrescrito. Documento que passa nessa validação limitada não é certificado como seguro; não há OCR nem processamento de PDF para texto neste ciclo.

Hash conhecido divergente impede download/análise/confirmar proposta. Legado sem hash é identificado como desconhecido, sem alteração retroativa. Download exige sessão, é attachment e não cacheia conteúdo. Relatórios não armazenam token e exibem somente dados oficiais, escapados. Mantenha DB, uploads, logs e backups sob permissões locais restritas; não compartilhe anexos/atestados ou dumps reais em issues.

Backup automático de startup copia DB consistentemente, mantém sete diários/dez pré-migração somente por nomes gerenciados. Backup portátil inclui uploads e mantém conjuntos completos sem retenção automática; consulte RECUPERACAO-DISTRIBUICAO.md. Não aplique política de descarte a batidas, snapshots ou anexos históricos. Prazo de retenção organizacional não foi inventado nesta iniciativa.

Auditoria de dependências: `python backend/tests/auditar_dependencias.py` consulta somente nomes/versões fixados na API pública OSV e salva o resultado. Levantamento de 2026-10-10: 25 pacotes, zero advisories retornados, sem certificação de segurança. Binário Python e SO exigem sua própria manutenção. Windows foi executado; CI Linux permanece para homologação fora desta máquina. Decisões e limites detalhados no ADR 0010.
