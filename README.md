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
- `N`, `F`, `A`, `R` e `C`: situação normal, falta, atestado, revisar e conferir.

Os atalhos de uma tecla ficam desativados durante a edição de campos de texto.

## Estrutura

```txt
backend/
  app/
    empresas/
    funcionarios/
    competencias/
    arquivos/
    marcacoes/
    apuracao/
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

## Importador TXT de relógio

O fluxo integrado aceita, nesta etapa, somente TXT estruturado com colunas separadas por TAB e cabeçalho contendo `EnNo`, `Name` e `DateTime`. O arquivo pode estar em UTF-16, UTF-8 com BOM ou UTF-8. A análise salva o original e gera uma prévia, mas só cria marcações depois da confirmação dos registros selecionados.

Endpoints:

- `POST /importadores/txt-log-relogio/analisar`: recebe `empresa_id`, `competencia_id` e `arquivo` como multipart;
- `POST /importadores/txt-log-relogio/confirmar`: recebe o arquivo analisado e os IDs selecionados;
- `GET /arquivos/{arquivo_id}/download`: devolve o original preservado.

Para uma demonstração inteiramente fictícia, use `backend/tests/fixtures/relogio_ficticio.txt`:

1. Ligue backend e frontend e confirme o indicador `Ambiente integrado`.
2. Cadastre ou edite a empresa pela tela **Empresas**, os funcionários pela área **Funcionários** da empresa e a competência pela área **Competências**. Esses formulários persistem os dados na API. O campo **Código** do funcionário deve corresponder ao `EnNo`; o nome exato normalizado é usado somente como segunda tentativa.
3. Abra `Empresa Demonstração → 07/2026 → Importações`, selecione a fixture e clique em `Analisar arquivo`.
4. Confira na prévia as batidas, pendências, funcionários não cadastrados e datas fora da competência. Estas últimas começam desmarcadas.
5. Selecione os dias desejados e clique em `Salvar importação e iniciar conferência`.
6. Na Conferência, abra um dia, confirme os segundos em `Batidas originais`, edite a interpretação e recarregue a página para validar a persistência.

A fixture não contém dados pessoais. Nela, `F001` é localizado, `X999` permanece propositalmente sem cadastro e uma data de junho aparece fora da competência de julho. A migração SQLite é aplicada automaticamente e de forma incremental ao iniciar a API; o banco existente não é recriado.

## Fluxo principal

1. Cadastre uma empresa na tela **Empresas**.
2. Abra a empresa e cadastre seus funcionários, informando o código usado pelo relógio.
3. Crie e abra uma competência mensal na área **Competências**.
4. Analise o TXT estruturado e revise a prévia.
5. Confirme somente os registros desejados.
6. Abra a **Conferência**, compare os originais e ajuste a interpretação quando necessário.
7. Recarregue e confirme a persistência da edição.
8. Marque os registros revisados como conferidos.
9. Consulte o **Resumo** real da competência.
10. Baixe o Excel em **Exportações**.
11. Feche a competência; para voltar a editar, use a ação explícita de reabertura.

## Endpoints principais

- `GET/POST /empresas` e `GET/PATCH /empresas/{id}`
- `GET/POST /funcionarios` e `GET/PATCH /funcionarios/{id}`
- `GET/POST /competencias` e `GET/PATCH /competencias/{id}`
- `POST /competencias/{id}/fechar`
- `POST /competencias/{id}/reabrir`
- `GET/POST /arquivos`
- `GET /arquivos/{arquivo_id}/download`
- `POST /importadores/txt-log-relogio/analisar`
- `POST /importadores/txt-log-relogio/confirmar`
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

Há código experimental anterior para XLSX/OCR no repositório, mas ele não integra o fluxo homologado deste MVP e não deve ser apresentado como funcionalidade suportada.

Consulte [CHECKLIST-CONGELAMENTO-MVP.md](CHECKLIST-CONGELAMENTO-MVP.md) para o aceite, as evidências e as limitações conhecidas.

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
