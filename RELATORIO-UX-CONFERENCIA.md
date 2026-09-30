# Identidade e UX da Conferência — 30/09/2026

## Base e preservação

- Repositório autorizado: `C:\Users\icaua\Documents\GitHub\OnPonto`.
- Branch: `main`; commit inicial: `abe49f03874fe223e4d6d4d79859d6085640f7c7` — Implementa confiabilidade operacional e políticas.
- Status inicial limpo, 1 commit à frente e 1 atrás de `origin/main`. Não houve sincronização remota.
- Backup completo: `C:\Users\icaua\Documents\OnPonto-backups\OnPonto_backup_pre_ux_conferencia_20260930-1915.zip`.
- ZIP fora da aplicação e do repositório (não é candidato a versionamento), 92.915.949 bytes, 4.337 entradas; CRC de todas as entradas verificado.
- Inclui Git, ambiente local, banco, uploads e demais arquivos. O banco operacional permaneceu byte a byte igual ao backup durante o desenvolvimento.
- Nenhuma worktree criada; nenhum push, merge ou publicação.
- Commit local desta rodada: `feat: improve employee identity and attendance review UX`.

## Migração e identidade

Migração aditiva SQLite 12 em `backend/app/database/migrations.py`, transacional e idempotente.
Acrescenta `funcionarios.nome_exibicao VARCHAR(180) NULL` e `codigo_exibicao VARCHAR(50) NULL`.
Não altera IDs internos, nomes/códigos de origem ou relacionamentos. Valores em branco viram NULL.
A migração está preparada para a inicialização normal da API; não foi aplicada ao banco operacional nesta validação.

O cadastro distingue nome/código originais dos campos de exibição. A apresentação usa o personalizado
ou, quando ausente, a identidade anterior. A normalização central do frontend atende cadastros,
Conferência, seletores, Ocorrências e navegação. Apuração, resumo, relatórios, espelhos e banco de
horas recebem os nomes de apresentação do backend. Os dados de origem continuam disponíveis na
edição e na seção “Identificação no ponto”. Os parsers e a associação automática não foram alterados.

## Contratos de API

- `POST /funcionarios` e `PATCH /funcionarios/{id}` aceitam os dois campos opcionais de exibição.
- `GET /funcionarios` e `GET /funcionarios/{id}` devolvem esses campos e os campos derivados
  `nome_apresentacao`/`codigo_apresentacao`, mantendo `nome`/`codigo` originais.
- `GET /funcionarios?q=...` pesquisa nome/ID de exibição e nome/código original, sem distinguir
  acentos ou caixa. A ordenação usa nome apresentado normalizado, com ID interno como desempate.
- `GET /apuracao` e `GET /apuracao/{id}`: `resumo[].problemas` continua sendo a fonte única da
  contagem por funcionário; `aguardando_conferencia` permanece separado. Os dias acrescentam
  `problema_rotulo`, `bloqueante` e, nos dias dentro do vínculo, `quantidade_batidas_originais`.
  O resumo inclui `nome_original` e `codigo_original`, com `funcionario`/`codigo` para apresentação.
- Banco de horas: apenas nomes apresentados nas respostas de resumo/extrato/alertas e em mensagem
  de bloqueio. Nenhuma regra, cálculo, política ou lançamento foi modificado.
- A atribuição assistida reutiliza `PATCH /marcacoes/{id}`; não cria endpoint nem outra trilha de gravação.

## Operação da Conferência

- Busca local nas quatro identidades, tanto no cadastro da empresa quanto na Conferência.
- Seletor mostra nome, ID apresentado e contagem de problemas da apuração; sem resposta, mostra “—”.
- “Próximo com problema” segue a ordem do seletor, pula funcionários limpos e não retorna ao início.
  Ao chegar ao fim, desabilita com “Sem próximo com problema”. Funcionários anteriores podem ser
  acessados pelo seletor ou pelas setas. Navegar pelas setas limpa o filtro de busca para manter
  visível a pessoa selecionada; o botão de problemas ativa o filtro de dias problemáticos.
- Coluna “Atenção” antes dos horários, com ícone e texto do backend. Dias problemáticos não recebem
  selo Normal, inclusive no painel de detalhes e no renderizador alternativo.
- Cabeçalho compacto, etapas e recursos na mesma faixa, grade dimensionada à viewport e painel
  com ações compactas. A observação secundária pode exigir rolagem; o motivo principal fica visível.

## Batidas ímpares

Para dias com até quatro batidas originais, o painel oferece a atribuição humana a Entrada 1,
Saída 1, Entrada 2 ou Saída 2. A ação não preenche automaticamente os demais campos. Bloqueia campo
ocupado, batida já usada e sequência inválida; exige reabrir dias conferidos e respeita competência
fechada. Horários seguem a precisão de minutos da edição existente; a origem mantém os segundos.

A alteração usa a mesma fila de autosave, auditoria persistida e pilha de desfazer da edição manual.
O backend rejeita confirmação enquanto houver problema. Atribuir apenas duas de três batidas
mantém bloqueio operacional, mesmo que essas duas formem entrada/saída. Completar a interpretação
resolve a pendência conforme as validações existentes. As batidas brutas nunca são reescritas.

## Testes e evidências

- Backend completo: **288 testes passaram**, incluindo 7 novos testes em `test_identidade_conferencia.py`.
- Frontend completo: **73 testes passaram**, incluindo 9 novos testes em `identidade-conferencia.test.cjs`.
- Cobertura nova: fallback/personalização; busca nas quatro identidades; colisão entre ID de exibição
  e código de relógio; migração idempotente preservando dados; contagem sem dias apenas aguardando;
  navegação que pula limpos e termina; ausência de selo Normal; batida ímpar bloqueante;
  atribuição, duplicação, ordem, auditoria, preservação de origem e desfazer.
- `python -m compileall -q backend/app backend/tests seed_demo.py`: passou.
- `node --check`: passou nos JavaScripts do frontend.
- `git diff --check`: passou.
- Chrome headless com API real e SQLite temporário fictício: busca, identidade, próximo com problema,
  atribuição, autosave, auditoria e undo persistido passaram, sem erros JavaScript.
- 1366×768: grade começa em ~335 px, termina em 756 px, 9 linhas completas visíveis.
- 1920×1080: grade começa em ~335 px, termina em 1068 px, 17 linhas completas visíveis.
- Em ambas as resoluções, motivo do problema visível sem rolagem horizontal e sem overflow da página.
- Capturas e logs: `C:\Users\icaua\Documents\OnPonto-backups\validacao_ux_conferencia_20260930-1915`.

Comandos principais, executados a partir do repositório:

```powershell
.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
node --test frontend/tests/*.test.cjs
.venv\Scripts\python.exe -m compileall -q backend/app backend/tests seed_demo.py
git diff --check
node frontend/tests/conferencia-browser.cjs
```

O teste de navegador usa Playwright disponível no ambiente; pode receber `ONPONTO_NODE_MODULES`,
`ONPONTO_PYTHON` e `ONPONTO_BROWSER_CHANNEL`. No Windows, usa Chrome instalado por padrão.
Ele cria banco/servidores temporários com dados fictícios e encerra os processos que iniciou.

## Arquivos alterados

- `backend/app/database/models.py`, `backend/app/database/migrations.py`
- `backend/app/funcionarios/schemas.py`, `backend/app/funcionarios/routes.py`
- `backend/app/apuracao/operacional.py`, `backend/app/apuracao/service.py`
- `backend/app/banco_horas/routes.py`, `backend/app/banco_horas/service.py` (apenas apresentação)
- `backend/tests/test_identidade_conferencia.py`, `backend/README.md`
- `frontend/app.js`, `frontend/index.html`, `frontend/styles.css`
- `frontend/js/utils.js`, `frontend/js/components.js`, `frontend/js/screens.js`
- `frontend/tests/identidade-conferencia.test.cjs`, `frontend/tests/conferencia-browser.cjs`
- `RELATORIO-UX-CONFERENCIA.md`

## Limitações e pendências

- Mais de quatro batidas permanecem disponíveis para consulta e correção manual. Não foi criada
  interpretação automática nem assistente para jornadas com mais de quatro campos.
- Snapshots de competências já fechadas preservam a identidade congelada; não foram reescritos
  após personalizar nomes. Novas apurações e novos fechamentos usam a identidade de exibição.
- Pendências de importação sem funcionário resolvido continuam na área de Importações, sem
  atribuição artificial à contagem de uma pessoa.
- No modo demonstração ou sem apuração disponível, não se inventa contagem de problemas:
  o seletor mostra “—” e a navegação por problemas fica indisponível.
- A suíte emite avisos preexistentes sobre `datetime.utcnow()`; nenhum teste falhou.
- A branch já estava divergente do remoto. Essa situação permanece, conforme o pedido de não
  fazer push/merge. Reinicie a API local para carregar o código e aplicar a migração 12.
- Importação em massa, reimportação, autenticação e novas regras de banco ficaram fora do escopo.
