# OnPonto

Sistema web para **tratamento, conferência e apuração de ponto recebido por escritórios contábeis**.

**Versão declarada:** `1.0.0-rc.1`
**Estado:** desenvolvimento ativo.

O OnPonto não é um relógio de ponto e não substitui o sistema oficial utilizado pelo empregador para registrar a jornada. Seu objetivo é receber os arquivos enviados pelos clientes, preservar os dados originais, organizar a conferência, tratar ocorrências e produzir resultados para a rotina de Departamento Pessoal.

O fluxo principal é:

```text
Empresa
→ Escalas
→ Funcionários
→ Competência
→ Importação
→ Conferência
→ Ocorrências e correções
→ Resumo
→ Exportações
→ Fechamento
```

---

## Principais recursos

Atualmente o OnPonto possui:

* cadastro de empresas;
* cadastro de escalas de trabalho;
* cadastro de funcionários;
* competências mensais;
* importação de arquivos de ponto em TXT e XLSX;
* detecção automática dos formatos suportados;
* preservação do arquivo original recebido;
* conferência diária por funcionário;
* edição e correção das marcações interpretadas;
* preservação das batidas originais;
* autosave das alterações;
* histórico de alterações;
* filtros de conferência;
* ações individuais e em massa;
* fechamento e reabertura de competências;
* snapshot da apuração no fechamento;
* ocorrências e afastamentos;
* atestados integrais e parciais;
* declarações;
* férias;
* afastamentos;
* folga compensatória;
* espelho de ponto individual;
* espelhos em lote;
* exportação para Excel;
* relatórios para impressão/PDF;
* banco de horas por escala;
* extrato e saldo de banco de horas;
* ajustes manuais auditáveis;
* alertas de vencimento;
* compensação FIFO dos lançamentos.

---

## Stack

### Backend

* Python
* FastAPI
* SQLAlchemy
* SQLite

### Frontend

* HTML
* CSS
* JavaScript puro

### Relatórios e arquivos

* openpyxl para Excel
* HTML preparado para impressão/PDF
* armazenamento local dos arquivos originais e anexos

A aplicação foi pensada inicialmente para execução local.

---

# Estrutura do projeto

```text
OnPonto/
├── backend/
│   ├── app/
│   │   ├── apuracao/
│   │   ├── arquivos/
│   │   ├── banco_horas/
│   │   ├── competencias/
│   │   ├── database/
│   │   ├── empresas/
│   │   ├── escalas/
│   │   ├── funcionarios/
│   │   ├── importadores/
│   │   ├── marcacoes/
│   │   ├── ocorrencias/
│   │   ├── relatorios/
│   │   └── main.py
│   ├── tests/
│   ├── uploads/
│   └── requirements.txt
│
├── frontend/
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   ├── js/
│   └── tests/
│
├── fixtures/
├── relatorios/
├── setup/
├── seed_demo.py
├── instalar_onponto.bat
├── instalar_onponto.sh
├── iniciar_onponto.bat
├── iniciar_onponto.sh
└── VERSION
```

---

# Fluxo de trabalho

## 1. Empresa

Cada cliente é cadastrado como uma empresa.

A empresa concentra suas competências, funcionários, escalas e configurações relacionadas à apuração.

---

## 2. Escalas

As regras de jornada ficam nas escalas, permitindo que uma mesma empresa possua funcionários com regimes diferentes.

As escalas podem definir, entre outras informações:

* modo de apuração;
* jornada;
* horários;
* sábado e domingo;
* tolerância de atraso;
* tolerância de hora extra;
* tolerância de intervalo;
* utilização de banco de horas.

---

## 3. Funcionários

Cada funcionário pertence a uma empresa e pode ser vinculado a uma escala.

O código cadastrado deve permitir a associação com os dados recebidos do sistema de ponto.

---

## 4. Competências

A apuração é organizada por competência mensal.

Dentro de uma competência ficam disponíveis áreas como:

* Resumo;
* Importações;
* Conferência;
* Arquivos;
* Histórico;
* Exportações.

Ao fechar uma competência, o OnPonto preserva um snapshot da apuração utilizada naquele fechamento.

A competência pode ser reaberta explicitamente caso seja necessária alguma correção.

---

# Importação de ponto

O fluxo de importação aceita atualmente arquivos:

```text
.txt
.xlsx
```

O sistema tenta identificar automaticamente o formato do arquivo antes de importar os registros.

Entre os layouts implementados estão:

```text
txt_log_relogio
txt_id_tempo_maquina
txt_generico
xlsx_ponto_generico
xlsx_cartao_ponto
```

O importador genérico de TXT possui tratamento conservador para diferentes:

* encodings;
* separadores;
* nomes de colunas;
* formatos de data;
* formatos de horário.

Quando não existe segurança suficiente para interpretar um registro, o sistema deve sinalizar a inconsistência em vez de inventar informações.

---

## Batidas

A interpretação preserva as marcações originais recebidas.

Uma quantidade diferente da esperada não é convertida silenciosamente em uma jornada completa.

Exemplos:

* quatro horários podem formar uma jornada completa;
* duas batidas permanecem como registro incompleto;
* quantidades atípicas ficam pendentes de conferência.

As batidas originais continuam disponíveis mesmo depois de ajustes na interpretação.

---

# Conferência

A Conferência é a principal área operacional do sistema.

Ela permite trabalhar funcionário por funcionário e dia por dia, comparando:

* jornada esperada;
* batidas originais;
* horários interpretados;
* atrasos;
* extras;
* ocorrências;
* abonos;
* pendências;
* situação da conferência.

As alterações são persistidas pela API.

A interface preserva o contexto de trabalho durante atualizações, incluindo a posição da tabela e o dia sendo conferido sempre que possível.

---

## Atalhos

Entre os atalhos disponíveis na Conferência:

```text
Ctrl + S       Salvar imediatamente
Ctrl + Z       Desfazer alteração
Alt + ↑ / ↓    Navegar entre funcionários

N              Normal
F              Falta
A              Atestado
C              Conferir
```

Atalhos de uma tecla são desativados durante edição de campos de texto.

---

# Ocorrências e afastamentos

O OnPonto possui módulo próprio para ocorrências.

São suportados, conforme o fluxo atualmente implementado:

* atestado;
* declaração;
* férias;
* afastamento;
* folga compensatória.

As ocorrências podem afetar a jornada exigida e os minutos abonados durante a apuração.

Atestados podem ser integrais ou parciais.

O cadastro de atestado também pode ser iniciado diretamente durante a Conferência, reutilizando o mesmo sistema de ocorrências.

---

## Anexos

As ocorrências podem receber documentos como:

```text
PDF
PNG
JPG
```

Os arquivos são armazenados localmente em:

```text
backend/uploads/
```

---

# Banco de horas

O banco de horas é um recurso opcional configurado por escala.

Uma empresa pode, portanto, possuir simultaneamente:

```text
Escala A → usa banco de horas
Escala B → não usa banco de horas
```

O banco é mantido separadamente da apuração mensal.

A apuração responde:

> O que aconteceu na jornada?

O banco de horas registra:

> Que crédito ou débito aquele resultado produziu?

---

## Ledger

Os lançamentos são registrados individualmente e podem representar:

* crédito;
* débito;
* ajuste manual;
* utilização por folga compensatória.

O saldo não é mantido como um número isolado editável.

Ele é derivado dos lançamentos e das compensações registradas.

---

## Compensação

Créditos e débitos são reconciliados de forma auditável.

As compensações registram explicitamente quais minutos de determinado crédito foram utilizados contra determinado débito.

O consumo prioriza os créditos de acordo com a política FIFO implementada.

---

## Vencimento

Créditos podem possuir data de vencimento.

Um crédito vencido não é automaticamente:

* apagado;
* pago;
* descontado;
* convertido em folha.

Ele é sinalizado para análise.

A decisão continua sendo responsabilidade do operador e das regras aplicáveis à empresa.

---

## Ajustes manuais

O banco permite ajustes manuais auditáveis.

Esses ajustes exigem justificativa e não substituem o registro normal da jornada quando o fato pode ser representado corretamente na apuração.

---

# Resumo da competência

O Resumo consolida os resultados calculados para os funcionários da competência.

As informações são derivadas da mesma apuração utilizada pela Conferência e pelos relatórios.

Competências fechadas utilizam o snapshot preservado no fechamento.

---

# Espelho de ponto

O OnPonto gera espelho individual por funcionário.

Na Conferência:

```text
Emitir espelho
```

O documento apresenta informações como:

* identificação;
* dias;
* batidas;
* ocorrências;
* abonos;
* totais;
* observações;
* campos para assinatura.

O documento é preparado para impressão em A4.

Também existe emissão em lote pela área de Exportações, com um espelho por funcionário.

---

# Exportações

A área de Exportações disponibiliza saídas destinadas à conferência e envio.

Entre elas:

* Excel;
* relatório para impressão;
* espelho individual;
* espelhos em lote.

---

# Instalação

## Requisitos

* Python 3
* Windows ou Linux
* portas locais `8000` e `5500` disponíveis

---

## Windows

Na primeira instalação:

```text
instalar_onponto.bat
```

Depois:

```text
iniciar_onponto.bat
```

Nas execuções seguintes, normalmente basta:

```text
iniciar_onponto.bat
```

---

## Linux

Dê permissão aos scripts:

```bash
chmod +x instalar_onponto.sh iniciar_onponto.sh
```

Instale:

```bash
./instalar_onponto.sh
```

Execute:

```bash
./iniciar_onponto.sh
```

---

# Endereços locais

Frontend:

```text
http://127.0.0.1:5500
```

API:

```text
http://127.0.0.1:8000
```

Swagger / OpenAPI:

```text
http://127.0.0.1:8000/docs
```

---

# Execução manual do backend

A partir da raiz:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

No Windows:

```bat
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

---

# Dados locais

Por padrão:

```text
Banco SQLite:
backend/onponto.db

Uploads:
backend/uploads/
```

Também podem ser utilizadas as variáveis:

```text
ONPONTO_DATABASE_URL
ONPONTO_UPLOADS_DIR
```

---

## Backup

Antes de atualizações importantes, preserve em conjunto:

```text
backend/onponto.db
backend/uploads/
```

O banco e os arquivos anexados fazem parte do mesmo conjunto operacional de dados.

---

# Migrações

O backend possui migrações SQLite incrementais executadas durante a inicialização.

O objetivo é evoluir o schema preservando os dados existentes, sem recriar o banco a cada atualização.

Os detalhes de cada evolução ficam registrados nos relatórios técnicos do projeto.

---

# Ambiente de demonstração

O projeto possui um seed com dados fictícios:

```bash
.venv/bin/python seed_demo.py
```

No Windows:

```bat
.venv\Scripts\python.exe seed_demo.py
```

O seed prepara dados de demonstração para testar o fluxo sem utilizar informações reais de clientes.

Ele pode ser executado novamente sem a intenção de duplicar os registros já existentes.

---

# Testes

## Backend

Linux:

```bash
.venv/bin/python -m unittest discover -s backend/tests -v
```

Windows:

```bat
.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

---

## Frontend

```bash
node --test frontend/tests/*.test.cjs
```

---

## Verificações adicionais

Python:

```bash
.venv/bin/python -m compileall -q backend/app backend/tests seed_demo.py
```

JavaScript:

```bash
node --check frontend/app.js
node --check frontend/js/screens.js
node --check frontend/js/components.js
```

Git:

```bash
git diff --check
```

---

# Limitações atuais

O OnPonto continua sendo uma aplicação voltada principalmente para operação local.

Entre as limitações atuais:

* não é um relógio oficial de registro de ponto;
* não possui autenticação multiusuário completa;
* não deve ser exposto diretamente à internet na configuração atual;
* novos layouts de ponto podem exigir novos adaptadores;
* OCR de cartões ou PDFs escaneados não faz parte do fluxo principal;
* o sistema não substitui análise trabalhista ou jurídica;
* banco de horas não calcula automaticamente valores financeiros de folha;
* decisões sobre pagamento, desconto ou tratamento de saldo vencido permanecem fora do escopo.

---

# Documentação técnica

Os detalhes das principais implementações e revisões estão em `relatorios/`.

* [Banco de horas](relatorios/RELATORIO-BANCO-DE-HORAS.md)
* [Conferência e atestados](relatorios/RELATORIO-CONFERENCIA-ATESTADOS.md)
* [Correções de integridade](relatorios/RELATORIO-CORRECAO.md)
* [Espelho de ponto](relatorios/RELATORIO-ESPELHO-PONTO.md)
* [Feriado e demissão](relatorios/RELATORIO-FERIADO-DEMISSAO.md)
* [Ocorrências e afastamentos](relatorios/RELATORIO-OCORRENCIAS-AFASTAMENTOS.md)
* [Resumo, admissão e calendário](relatorios/RELATORIO-RESUMO-ADMISSAO-CALENDARIO.md)
* [Revisão técnica e visual](relatorios/RELATORIO-REVISAO-TECNICA-VISUAL.md)
* [Tolerância e espelhos em lote](relatorios/RELATORIO-TOLERANCIA-ESPELHOS-LOTE.md)

O marco original do MVP permanece documentado em:

* [Checklist de congelamento do MVP](CHECKLIST-CONGELAMENTO-MVP.md)

---

# Sobre o projeto

O OnPonto nasceu para resolver uma rotina específica de escritório contábil: receber pontos de empresas diferentes, em formatos diferentes, conferir inconsistências manualmente e transformar esse material em uma apuração organizada e rastreável.

A prioridade do projeto é preservar a informação original e deixar explícito quando uma situação depende de conferência humana, evitando interpretar silenciosamente dados ambíguos.
