# On Ponto

Sistema web monolítico/modular para tratamento e apuração de ponto recebido por escritório contábil.

O On Ponto não é um sistema oficial de registro de ponto, não substitui relógio de ponto e não é usado para funcionários baterem ponto. O objetivo do MVP é receber arquivos enviados pelos clientes, organizar, conferir, apurar e manter histórico.

## Stack

- Backend: Python + FastAPI
- Banco: SQLite
- ORM: SQLAlchemy
- Frontend: HTML, CSS e JavaScript puro
- Excel: openpyxl
- PDF: relatório HTML imprimível com `window.print()`

## Protótipo de interface

O frontend atual é um protótipo desktop-first que funciona com dados simulados e não envia arquivos ou alterações ao backend. Essa separação é intencional: toda importação passa por uma prévia explícita antes de qualquer confirmação.

O protótipo permite:

- iniciar pela lista de empresas e navegar por visão geral, funcionários, competências, relatórios e configurações da empresa;
- abrir uma competência e acessar Resumo, Importações, Conferência, Arquivos, Histórico e Exportações sem perder o contexto;
- simular a análise de TXT, XLS, XLSX, PDF ou imagem e revisar a prévia sem salvar automaticamente;
- editar horários na grade de Conferência com normalização, validação, navegação por teclado e autosave simulado;
- comparar batidas originais, interpretação sugerida, edição atual e resultado conferido;
- selecionar dias, aplicar ações em massa com confirmação e abrir a comparação visual de OCR;
- demonstrar todos os estados de dia pedidos com 248 registros fictícios de julho de 2026.

Como o frontend continua sendo um protótipo estático, a hierarquia usa rotas hash, por exemplo
`#/empresas/1/competencias/1001/conferencia`. Isso preserva deep links e recarregamento com
`python -m http.server`, que não oferece fallback de SPA para caminhos físicos.

Os dados detalhados da Conferência (dias, batidas, painel e autosave) estão simulados para
Queen · 07/2026. As demais empresas e competências mantêm seus resumos e podem apresentar
estados vazios nas áreas em que os mocks não possuem registros detalhados.

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
```

## Como rodar

1. Instale e execute o backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

2. Abra o frontend:

Abra `frontend/index.html` no navegador. Para a validação mais fiel, prefira servi-lo por HTTP:

Se preferir servir por HTTP:

```bash
cd frontend
python -m http.server 5500
```

Depois acesse http://127.0.0.1:5500.

O backend não precisa estar ligado para usar o protótipo. O modo de demonstração aparece de forma explícita em todas as telas.

## Fixtures para testes

O projeto inclui um gerador de arquivos fictícios de ponto para testar upload, histórico, conferência manual, apuração e futuras leituras por OCR.

Esses dados são inventados e não devem ser usados como registro oficial de ponto.

Para instalar as dependências do gerador no mesmo ambiente virtual do backend:

```bash
backend\.venv\Scripts\python -m pip install -r fixtures\requirements.txt
```

Para gerar novamente os arquivos:

```bash
backend\.venv\Scripts\python fixtures\generate_fixtures.py
```

Arquivos gerados:

- PDFs: `fixtures/generated/pdf/`
- Imagem PNG degradada: `fixtures/generated/images/`
- Planilha XLSX: `fixtures/generated/spreadsheets/`
- Resultado esperado JSON: `fixtures/generated/expected/resultado_esperado.json`

O gerador cria relatórios simples, bagunçados e com inconsistências para as empresas fictícias Mercado Exemplo LTDA, Padaria Modelo LTDA e Loja Teste Comércio LTDA, com funcionários fictícios e situações como falta, atestado, folga, feriado, sábado, domingo, hora extra, atraso e marcação incompleta.

## Fluxo principal

1. Cadastre uma empresa.
2. Cadastre funcionários vinculados à empresa.
3. Crie uma competência mensal.
4. Faça upload dos arquivos originais recebidos.
5. Importe planilhas XLSX legadas, quando houver.
6. Lance ou confira as marcações de ponto.
7. Veja a apuração.
8. Exporte Excel ou abra o relatório imprimível para salvar em PDF pelo navegador.

## Importador XLSX legado

A tela `Importar XLSX` aceita planilhas antigas em que cada funcionário ocupa um bloco de 3 linhas: cabeçalho, marcações e dias do mês.

O importador:

- salva o XLSX original no histórico da competência;
- lê horários múltiplos em uma mesma célula usando `openpyxl`;
- retorna uma prévia estruturada;
- marca dados importados como `origem = xlsx_importado`;
- mantém `conferido = false`;
- usa `pendente_conferencia` quando a quantidade de marcações exige revisão manual.

Endpoint:

- `POST /importadores/xlsx-ponto-generico`

## Endpoints principais

- `GET/POST/PATCH /empresas`
- `GET/POST/PATCH /funcionarios`
- `GET/POST/PATCH /competencias`
- `GET/POST /arquivos`
- `POST /importadores/xlsx-ponto-generico`
- `GET/POST/PATCH /marcacoes`
- `GET /apuracao`
- `GET /relatorios/excel`
- `GET /relatorios/impressao`
