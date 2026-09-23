# Revisão técnica e visual — On Ponto

Concluída em 11/09/2026. Revisão incremental do MVP, sem troca de arquitetura ou framework.

## Alterações realizadas

- Paleta oficial centralizada no CSS: sidebar `#103C32`, ações principais `#16845B`, confirmação verde clara, informação neutra cinza, conferência amarela e erro vermelho. Foco visível, controles nativos, seleção, links, ocorrências e dados de demonstração alinhados. As linhas confirmadas continuam neutras, com indicadores.
- Ajustados raios, contraste, tabelas com scroll interno, abas em janelas estreitas e altura dos modais. O contexto de empresa/competência permanece visível. A logo existente foi preservada.
- TXT genérico mantém repetições, segundos e ordem das batidas originais; a lista ordenada usada na interpretação é separada. Datas sem horário não viram meia-noite. Horários inválidos e linhas não interpretadas são sinalizados; o arquivo original continua preservado.
- Associação do TXT genérico recusa ID divergente, nomes conflitantes e homônimos. Layouts inferidos sem cabeçalho exigem seleção humana. Os parsers TXT conhecidos continuam prioritários e seus arquivos não foram alterados; a camada de prévia sinaliza divergência de cadastro e remove a seleção automática desses candidatos.
- Autosave envia uma gravação por vez, preserva a edição mais recente após falha e protege alterações pendentes durante recarga de dados. O navegador avisa ao sair com edição ou envio pendente. “Salvo” depende da resposta da API.
- Arquivos recebem resumo persistido de formato, encoding, linhas interpretadas/rejeitadas, dias pendentes e confirmações com data, importados e conflitos. Os avisos não substituem o arquivo original.
- Excel manteve o cabeçalho verde já existente. Relatórios HTML usam tokens da marca. Espelhos mantêm A4 retrato, lote, snapshot e assinatura da empresa; a assinatura do funcionário agora mostra seu nome.

## Causa do azul

- **Arquivo:** `frontend/styles.css`.
- **Regras/classes:** tokens `--navy-*`, `--blue-*`; `.sidebar`, `.button--primary`, links, foco, abas, seleção de tabela e estilos de ocorrências. Havia também cores diretas, como `#1b77ca` e `#eaf4fe`.
- **Causa:** paleta azul anterior ainda aplicada aos componentes próprios. O projeto não usa Bootstrap. `frontend/js/mocks.js` também continha cores azuis e roxas nos dados demonstrativos.

## Arquivos alterados

- `frontend/styles.css` — tokens, estados, foco, contraste e responsividade.
- `frontend/app.js` — fila sequencial de salvamento, proteção de edição e aviso de saída.
- `frontend/js/screens.js` — Salvar agora como ação principal.
- `frontend/js/mocks.js` — cores demonstrativas alinhadas à marca.
- `frontend/index.html` — versão dos recursos para invalidar cache antigo.
- `backend/app/importadores/txt_generico.py` — integridade, identificação e leitura conservadora de datas/horários.
- `backend/app/importadores/routes.py` — avisos de associação e rastreabilidade persistida.
- `backend/app/relatorios/routes.py` — paleta dos documentos e identificação das assinaturas.
- Novos: `backend/tests/test_revisao_mvp.py`, `frontend/tests/autosave-revisao.test.cjs` e `frontend/tests/layout-marca.html` — regressão e medição visual.

Motor de apuração, migrações, ocorrências, parsers conhecidos e testes anteriores foram preservados. O banco operacional não foi alterado durante a revisão; testes de persistência usaram bancos e arquivos isolados.

## Testes

- **Executados: 188 testes; passaram: 188; falharam: 0.** Backend: 173; frontend: 15. Antes desta rodada, o backend tinha 162 testes.
- A matriz TXT cobre **216 combinações** dentro de um teste parametrizado: UTF-8/UTF-16/CP1252, TAB/`;`/`|`/`,`, três formatos de data/hora e seis grupos de aliases.
- Cenários adicionais: arquivo vazio, cabeçalho sem dados, linha inválida, nome/ID ausente, identificação ambígua, duplicatas, ordem inversa, segundos e uma a seis batidas. Arquivo e batidas foram comparados após edição e reimportação; duplicidade não sobrescreveu o dia existente.
- Mantidos os testes de importação integrada, isolamento empresa/competência, fechamento, ocorrências, Excel e espelhos individual/lote. Nenhum teste anterior teve sua expectativa alterada.
- Sintaxe JavaScript e compilação Python aprovadas. Navegação visual inspecionada no navegador; medições de Conferência em 1280, 1024, 720 e 480 px. Testes visuais usam dados demonstrativos; não representam certificação completa de acessibilidade ou de todas as telas.
- Contrastes calculados: branco/verde principal **4,68:1**; texto da sidebar **10,58:1**; aviso **7,22:1**; erro **6,76:1**; texto secundário/fundo **5,25:1**.

Evidências: [backend](logs/testes-revisao-marca-final.txt), [frontend](logs/testes-revisao-marca-frontend.txt), [medição visual](logs/validacao-visual-marca.json), [alterações](logs/alteracoes-revisao-marca.diff) e [fontes preservados](logs/fontes-revisao-marca.json). Cópia anterior: `logs/fontes-antes-revisao-marca.zip`.

## Problemas encontrados que ainda não foram corrigidos

**CRÍTICO:** nenhum problema crítico residual confirmado nesta revisão. Isso não equivale a garantia de ausência de defeitos.

**ALTO:** edição do mesmo dia em duas janelas não possui controle de versão para rejeitar uma gravação desatualizada; a última gravação pode prevalecer. A proteção da fila nesta entrega vale dentro da mesma janela.

**MÉDIO:** alterações ainda não enviadas ficam em memória. O aviso de saída ajuda no fechamento normal, mas não recupera rascunhos após encerramento forçado, queda de energia ou descarte deliberado do aviso. O lote de edições é persistido por dia, sem transação única envolvendo todos os dias; falhas são indicadas e mantidas para nova tentativa. O upload genérico de documentos em `/arquivos` não tem o limite explícito de 25 MB já existente na importação de ponto.

**BAIXO:** chamadas preexistentes a `datetime.utcnow()` geram avisos de depreciação. A fonte Inter depende de carregamento externo, com fallback local já configurado. Algumas medidas antigas de espaçamento foram mantidas para evitar redesenho desnecessário.

**MELHORIA FUTURA:** controle de versão por marcação, recuperação local de rascunhos e revisão assistida de linhas rejeitadas/associações. Essas funcionalidades não foram implementadas automaticamente.

## Próximos passos recomendados

1. Reiniciar a API e recarregar o frontend para usar a versão atualizada; revisar o fluxo com um arquivo real de cada equipamento utilizado.
2. Priorizar controle de edição concorrente antes de ampliar o uso para várias janelas ou operadores no mesmo dia.
3. Planejar recuperação de rascunhos e limite uniforme de upload. Até lá, aguardar a indicação de salvamento e manter o backup habitual de banco e arquivos.

O fluxo permanece: **empresa → competência → importação → análise → conferência → ajuste → confirmação → persistência → exportação**. Os riscos residuais acima impedem prometer ausência absoluta de perda de edições em qualquer condição.
