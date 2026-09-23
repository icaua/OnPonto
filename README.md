# On Ponto

Sistema web monolítico/modular para tratamento e apuração de ponto recebido por escritório contábil.

**Versão:** `1.0.0-rc.1`

**Estado:** candidato a MVP, com escopo funcional congelado em 15/08/2026.

O On Ponto não é um sistema oficial de registro de ponto, não substitui relógio de ponto e não é usado para funcionários baterem ponto. O objetivo do MVP é receber arquivos enviados pelos clientes, organizar, conferir, apurar e preservar as marcações e os arquivos originais.

## Stack

- Backend: Python + FastAPI
- Banco: SQLite
- ORM: SQLAlchemy
- Frontend: HTML, CSS e JavaScript puro
- Excel: openpyxl
- PDF: relatório HTML imprimível com `window.print()`

## Interface e fluxo integrado

O frontend desktop-first consulta a API em `http://127.0.0.1:8000` por padrão. Quando a API está disponível, empresas, funcionários, competências e marcações vêm do backend; se ela estiver offline, a interface sinaliza claramente o modo de demonstração e usa os mocks locais.

A interface permite:

- iniciar pela lista de empresas e navegar por visão geral, funcionários, competências, relatórios e configurações da empresa;
- abrir uma competência e acessar Resumo, Importações, Conferência, Arquivos, Histórico e Exportações sem perder o contexto;
- analisar um TXT estruturado, revisar a prévia, selecionar os registros e só então confirmar a importação;
- editar horários na grade de Conferência com normalização, validação, navegação por teclado e autosave persistido pela API;
- comparar as batidas originais com a interpretação atual e marcar o resultado como conferido;
- selecionar dias e aplicar ações em massa com confirmação, sem alterar as batidas originais;
- abrir o arquivo TXT original em modo somente leitura;
- consultar a apuração real, baixar o Excel e fechar ou reabrir a competência com proteção de escrita.

Como o frontend é servido como aplicação estática, a hierarquia usa rotas hash, por exemplo
`#/empresas/1/competencias/1001/conferencia`. Isso preserva deep links e recarregamento com
`python -m http.server`, que não oferece fallback de SPA para caminhos físicos.

No modo integrado, os dados detalhados da Conferência são recarregados por competência e continuam disponíveis após atualizar a página. As batidas originais mantêm os segundos do TXT e as edições alteram somente a interpretação atual. No fallback offline, permanecem disponíveis os dados fictícios de Queen · 07/2026.

Atalhos principais na Conferência:

- `Ctrl + S`: salvar imediatamente;
- `Ctrl + Z`: desfazer a última alteração confirmada;
- `Alt + ↑` / `Alt + ↓`: navegar entre funcionários;
- `N`, `F`, `A` e `C`: situação normal, falta, atestado e conferir.

Os atalhos de uma tecla ficam desativados durante a edição de campos de texto.

## Banco de horas por escala

O banco de horas é habilitado por escala, após configurar o prazo de compensação na empresa. O fechamento publica créditos e débitos diários, com compensações auditáveis e saldo separado da apuração mensal. O menu **Banco de horas** oferece extrato, ajustes com motivo, estornos e alertas; a ocorrência **Folga compensatória** registra o uso autorizado do saldo.

A migração de schema 9 é aplicada ao reiniciar o backend. Escalas existentes começam com o banco desabilitado e fechamentos antigos não recebem lançamentos automaticamente. As instruções de uso, validações e limitações do histórico de escala estão no [relatório do banco de horas](RELATORIO-BANCO-DE-HORAS.md).

## Estrutura

```txt
backend/
  app/
    empresas/
    escalas/
    funcionarios/
    competencias/
    arquivos/
    marcacoes/
    apuracao/
    banco_horas/
    relatorios/
    database/
    main.py
  tests/
  uploads/
  requirements.txt
frontend/
  index.html
  styles.css
  app.js
  js/
    mocks.js
    utils.js
    components.js
    screens.js
seed_demo.py
instalar_onponto.{sh,bat}
iniciar_onponto.{sh,bat}
VERSION
```

## Executando o On Ponto

Os scripts criam e usam a virtualenv `.venv` na raiz do projeto. Eles podem ser chamados de qualquer diretório e não apagam banco, uploads ou outros dados existentes.

Pré-requisitos:

- Python 3.10 ou mais recente;
- acesso à internet na primeira instalação para baixar as dependências Python;
- portas locais `8000` e `5500` livres.

O MVP foi preparado para uso local por uma pessoa, somente em `127.0.0.1`. Como não há autenticação nesta versão, não exponha esses serviços à rede. Antes de atualizar ou mover a instalação, faça uma cópia conjunta de `backend/onponto.db` e `backend/uploads/`; o produto não cria backups nem criptografa esses dados automaticamente.

### Windows

Primeira execução:

1. Execute `instalar_onponto.bat`.
2. Execute `iniciar_onponto.bat`.

Uso posterior:

1. Execute apenas `iniciar_onponto.bat`.

O inicializador abre backend e frontend em janelas separadas e, depois que os serviços respondem, abre o navegador. Para encerrar, feche as duas janelas de serviço.

### Linux

Primeira execução:

```bash
chmod +x instalar_onponto.sh iniciar_onponto.sh
./instalar_onponto.sh
./iniciar_onponto.sh
```

Uso posterior:

```bash
./iniciar_onponto.sh
```

O inicializador permanece aberto como supervisor. Use `Ctrl+C` para encerrar backend e frontend. Em ambiente gráfico ele tenta abrir o navegador com `xdg-open`; sem interface gráfica, apenas mostra a URL. Os logs ficam em `logs/backend.log` e `logs/frontend.log`.

### Endereços locais

Frontend:
http://127.0.0.1:5500

API:
http://127.0.0.1:8000

Swagger:
http://127.0.0.1:8000/docs

O backend precisa estar ligado para o fluxo real de importação e persistência. Sem ele, o frontend sinaliza explicitamente o modo de demonstração.

## Preparando a demonstração

Depois da instalação, execute o seed a partir da raiz do projeto:

Linux:

```bash
.venv/bin/python seed_demo.py
```

Windows:

```bat
.venv\Scripts\python.exe seed_demo.py
```

O comando prepara a **Empresa Demonstração**, a competência **07/2026** e dois funcionários fictícios, incluindo o código `F001` usado pela fixture TXT dos testes. Ele pode ser executado novamente sem duplicar ou apagar dados e informa o que criou ou reutilizou. O código fictício `X999` permanece sem cadastro de propósito, para demonstrar o tratamento de divergências na importação.

## Importação de ponto

O fluxo integrado aceita `.txt` ou `.xlsx` e detecta automaticamente qual dos quatro formatos suportados o arquivo segue — nunca "chuta" um layout parecido. Se nenhum adaptador reconhecer a estrutura, a análise recusa com um erro claro. A análise salva o original e gera uma prévia, mas só cria marcações depois da confirmação dos registros selecionados.

Formatos reconhecidos:

- `txt_log_relogio`: TXT TAB com colunas `EnNo`, `Name`, `DateTime` (UTF-16, UTF-8 com BOM ou UTF-8);
- `txt_id_tempo_maquina`: TXT TAB com colunas `ID`, `Nome`, `Tempo` (data `DD/MM/AAAA`, hora `HH:MM:SS`);
- `xlsx_ponto_generico`: XLSX em blocos por funcionário, marcados por uma célula com "NUMERO DE FUNCIONÁRIO";
- `xlsx_cartao_ponto`: XLSX "longo", uma linha por funcionário-por-dia, com os horários do dia numa única célula separados por `;`.

Quantidade de batidas diferente de 4 num dia nunca é adivinhada: 2 preenche só entrada/saída, qualquer outra quantidade (0, 1, 3 ou mais de 4) fica pendente para conferência humana, sem inventar qual horário é qual.

Endpoints:

- `POST /importadores/analisar`: recebe `empresa_id`, `competencia_id`, `mes`, `ano` e `arquivo` (`.txt` ou `.xlsx`) como multipart; a resposta inclui `tipo_detectado` com o formato reconhecido;
- `POST /importadores/confirmar`: recebe o arquivo analisado e os IDs selecionados;
- `GET /arquivos/{arquivo_id}/download`: devolve o original preservado.

Para uma demonstração inteiramente fictícia, use `backend/tests/fixtures/relogio_ficticio.txt`:

1. Ligue backend e frontend e confirme o indicador `Ambiente integrado`.
2. Cadastre ou edite a empresa pela tela **Empresas**, configure uma escala na área **Escalas**, vincule-a aos funcionários e crie a competência em **Competências**. Esses formulários persistem os dados na API. O campo **Código** do funcionário deve corresponder ao `EnNo`; o nome exato normalizado é usado somente como segunda tentativa.
3. Abra `Empresa Demonstração → 07/2026 → Importações`, selecione a fixture e clique em `Analisar arquivo`.
4. Confira na prévia as batidas, pendências, funcionários não cadastrados e datas fora da competência. Estas últimas começam desmarcadas.
5. Selecione os dias desejados e clique em `Salvar importação e iniciar conferência`.
6. Na Conferência, abra um dia, confirme os segundos em `Batidas originais`, edite a interpretação e recarregue a página para validar a persistência.

A fixture não contém dados pessoais. Nela, `F001` é localizado, `X999` permanece propositalmente sem cadastro e uma data de junho aparece fora da competência de julho. A migração SQLite é aplicada automaticamente e de forma incremental ao iniciar a API; o banco existente não é recriado.

## Fluxo principal

1. Cadastre uma empresa na tela **Empresas**.
2. Abra a empresa e cadastre ao menos uma escala de trabalho.
3. Cadastre os funcionários, vinculando a escala e informando o código usado pelo relógio.
4. Crie e abra uma competência mensal na área **Competências**.
5. Analise o arquivo de ponto (TXT ou XLSX) e revise a prévia.
6. Confirme somente os registros desejados.
7. Abra a **Conferência**, compare os originais e ajuste a interpretação quando necessário.
8. Recarregue e confirme a persistência da edição.
9. Marque os registros revisados como conferidos.
10. Consulte o **Resumo** real da competência.
11. Baixe o Excel em **Exportações**.
12. Feche a competência; para voltar a editar, use a ação explícita de reabertura.

## Endpoints principais

- `GET/POST /empresas` e `GET/PATCH /empresas/{id}`
- `GET/POST /escalas` e `GET/PUT/DELETE /escalas/{id}`
- `GET/POST /funcionarios` e `GET/PATCH /funcionarios/{id}`
- `GET/POST /competencias` e `GET/PATCH /competencias/{id}`
- `POST /competencias/{id}/fechar`
- `POST /competencias/{id}/reabrir`
- `GET/POST /arquivos`
- `GET /arquivos/{arquivo_id}/download`
- `POST /importadores/analisar`
- `POST /importadores/confirmar`
- `GET/POST /marcacoes` e `GET/PATCH /marcacoes/{id}`
- `GET /apuracao?competencia_id={id}`
- `GET /relatorios/excel?competencia_id={id}`
- `GET /relatorios/impressao?competencia_id={id}`

O `PATCH /competencias/{id}` não altera status nem data de fechamento. Essas transições passam exclusivamente pelas ações `fechar` e `reabrir`. Depois do fechamento, leituras e exportações continuam liberadas, enquanto importações, uploads e edições retornam conflito até a reabertura.

## Escopo congelado

O candidato `1.0.0-rc.1` cobre somente o caminho validado de TXT estruturado até o fechamento. Nesta etapa são aceitas apenas correções de bugs, pequenos ajustes de UX e acessibilidade, textos, regressões e documentação.

Ficam explicitamente para versões posteriores:

- importação XLS legado e suporte a novos formatos XLSX;
- OCR e processamento de PDF escaneado;
- recursos de IA e leitura automática de atestados;
- autenticação e permissões avançadas;
- motor completo de regras trabalhistas.

O marco original de congelamento validava TXT. A implementação atual também integra os dois formatos XLSX listados na seção de importação, com testes automatizados; outros layouts e OCR continuam fora do suporte.

## Correções de integridade — 07/09/2026

O fechamento preserva uma cópia da apuração usada em consultas e exportações. Alterações posteriores de escalas ou funcionários não modificam esse resultado. A reabertura descarta essa cópia e permite nova apuração com as regras atuais. Consultas a competências fechadas não geram dias de calendário.

Ao iniciar a API, a migração para o schema 4 adiciona os campos de preservação e histórico. Para competências já fechadas, o sistema preserva os dados disponíveis na atualização, sem gerar dias; não consegue recuperar regras históricas que já tenham sido alteradas. Faça backup conjunto do banco e dos uploads antes da atualização, como indicado nas instruções de execução.

Edições de marcações pela API registram data/hora, campos e valores anteriores/posteriores na mesma transação. O histórico é carregado novamente na Conferência. Eventos anteriores à atualização não podem ser reconstruídos, e o ator continua sendo “Operador local”, pois o MVP não possui autenticação. Horários informados devem respeitar a ordem cronológica; dias incompletos continuam disponíveis para conferência.

Veja [RELATORIO-CORRECAO.md](RELATORIO-CORRECAO.md) para escopo e evidências.

Consulte [CHECKLIST-CONGELAMENTO-MVP.md](CHECKLIST-CONGELAMENTO-MVP.md) para o aceite, as evidências e as limitações conhecidas.

## Ocorrências e afastamentos

O menu da empresa possui a tela **Ocorrências / Afastamentos**, integrada à apuração. Cadastre atestados, declarações de horas, férias e afastamentos, filtre por funcionário/competência/período e consulte o histórico persistente. Anexos PDF, PNG ou JPG de até 25 MB são armazenados em uploads.

Ocorrências integrais retiram a jornada exigida; declarações e atestados parciais abonam somente a ausência coberta quando há escala de horário fixo e batidas completas. Casos sem dados suficientes ficam pendentes. Operações que atingem competências fechadas são bloqueadas até sua reabertura. Batidas originais e snapshots existentes são preservados.

O módulo de ocorrências foi introduzido no schema 5; a versão atual é o schema 6, descrito abaixo. Antes de atualizar, preserve uma cópia conjunta do banco e dos uploads. Consulte [RELATORIO-OCORRENCIAS-AFASTAMENTOS.md](RELATORIO-OCORRENCIAS-AFASTAMENTOS.md) para arquitetura, endpoints, limites e evidências de validação.

## Espelho de ponto individual

Na **Conferência**, selecione o funcionário e clique em **Emitir espelho**. O documento abre em nova aba, com dias, ocorrências, abonos, totais e campos de assinatura e data. Use **Imprimir / Salvar PDF** no próprio documento. Salve as edições pendentes antes da emissão.

A rota `GET /relatorios/espelho-ponto?competencia_id=...&funcionario_id=...` usa a mesma apuração dos demais relatórios e os snapshots de competências fechadas. Cargo vem do cadastro atual, identificado no documento; nome e código vêm da apuração preservada. Dias sem cálculo confiável exibem valores indisponíveis e mantêm seus motivos de pendência.

Veja [RELATORIO-ESPELHO-PONTO.md](RELATORIO-ESPELHO-PONTO.md) para as correções e evidências da revisão. Os testes do fluxo de emissão e do saldo no frontend podem ser executados com `node --test frontend/tests/espelho.test.cjs`.

## Tolerância de intervalo e espelhos em lote

No cadastro de escala, deixe **Tolerância de intervalo** vazia para seguir a tolerância geral de atraso. Digitar **0** define tolerância zero. A API preserva essa distinção: `null` significa herdar; omitir o campo em uma atualização mantém o valor anterior.

Ao iniciar a API, o schema 6 permite `NULL` nessa coluna e converte os zeros históricos existentes para `NULL`, uma única vez. Valores positivos permanecem. Zeros explícitos salvos após a migração permanecem zero nas próximas inicializações. Na cópia de validação do banco deste projeto, **1 escala (ID 1)** foi convertida; se essa escala precisava de zero deliberado, preencha **0** após atualizar. O banco original não foi modificado nesta validação.

Os espelhos agora usam **A4 retrato, margens de 10 mm**. Em **Exportações**, clique em **Abrir espelhos** no cartão **Espelhos de ponto (todos os funcionários)**. A rota `GET /relatorios/espelho-ponto-lote?competencia_id=...` apura uma vez e usa o mesmo conteúdo da emissão individual. Cada funcionário começa em uma nova página; notas extensas podem exigir continuação. O botão individual **Emitir espelho** permanece na Conferência.

O lote inclui todos os funcionários do resumo, inclusive os sem marcações, com aviso de ausência de dados. Se o resumo estiver vazio, retorna HTML com a mensagem “Nenhum funcionário disponível nesta competência.” (HTTP 200). Competência inexistente retorna 404. Competências fechadas mantêm seu snapshot.

Consulte [RELATORIO-TOLERANCIA-ESPELHOS-LOTE.md](RELATORIO-TOLERANCIA-ESPELHOS-LOTE.md) para a contagem da migração, medições de impressão e testes. Execute todos os testes de frontend com `node --test frontend/tests/*.test.cjs`.

## Testes

No ambiente virtual do backend:

```bash
.venv/bin/python -m unittest discover -s backend/tests -v
```

No Windows, use `.venv\Scripts\python.exe` no lugar de `.venv/bin/python`. Verificações adicionais usadas no congelamento:

```bash
.venv/bin/python -m compileall -q backend/app backend/tests seed_demo.py
node --check frontend/app.js
node --check frontend/js/screens.js
node --check frontend/js/components.js
bash -n instalar_onponto.sh iniciar_onponto.sh
git diff --check
```
