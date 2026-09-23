# Entrega — Ocorrências e Afastamentos

Data: 07/09/2026. Resultado: implementado e validado no projeto On Ponto.

## Estado inicial e resultado

- Antes das alterações: **106 testes aprovados** em 11,070 s; schema SQLite 4.
- Após a implementação: **134 testes aprovados**, sem falhas ou erros, em 13,763 s.
- Foram adicionados **28 testes de regressão**.
- `compileall` passou para backend, testes e seed.
- `node --check` passou para `app.js`, `screens.js`, `components.js` e `ocorrencias.js`.
- A migração 4 → 5 foi executada duas vezes sobre uma cópia do banco operacional. Todas as linhas e campos das seis tabelas preexistentes foram preservados.
- `PRAGMA integrity_check`: `ok`; `PRAGMA foreign_key_check`: nenhuma violação.
- O banco operacional e os uploads originais **não foram alterados** nesta execução. A validação visual utilizou um banco fictício separado.

Evidências: [suíte inicial](logs/testes-ocorrencias-antes.txt), [suíte final](logs/testes-ocorrencias-final.txt), [migração](logs/migracao-ocorrencias.json), [estado inicial e hashes](logs/estado-inicial-ocorrencias.json), [fontes anteriores à implementação](logs/fontes-antes-ocorrencias.zip).

## Arquitetura escolhida

Uma entidade `OcorrenciaFuncionario`, na tabela `ocorrencias_funcionario`, ligada por chave estrangeira a `funcionarios`. A empresa é obtida pelo funcionário, evitando duplicação de `empresa_id` no banco; esse campo é retornado pela API para facilitar filtros e apresentação.

O modelo contém tipo, início/fim, horários opcionais, observação, referência/nome do anexo, `created_at` e `updated_at` no padrão existente, `excluido_em` e histórico JSON. Os quatro tipos iniciais são `ATESTADO`, `DECLARACAO`, `FERIAS` e `AFASTAMENTO`. Acrescentar tipos não exige criar uma tabela por tipo.

A exclusão é lógica: remove a ocorrência da apuração e da listagem padrão, preservando registro, anexo e auditoria. A consulta com `incluir_excluidas=true` permite localizar registros excluídos e consultar seu histórico. Não foi implementada restauração pela interface.

O fluxo permanece:

**Importação → Conferência → Escala + Batidas + Ocorrências + Calendário → Apuração → Resultado → Relatórios.**

O módulo possui schemas, rotas, serviço de cadastro e um interpretador separado. A interpretação de ocorrências fica em `ocorrencias/interpretacao.py`; o serviço principal de apuração carrega as ocorrências da competência uma vez e aplica o resultado a cada dia. Nenhuma ocorrência modifica os horários da marcação nem suas batidas originais.

## Migration e proteção dos fechamentos

O mecanismo incremental existente passa ao **schema 5** e cria a nova tabela e seus índices com `checkfirst=True`, dentro da transação da migração. A inicialização habitual da API continua sendo suficiente para atualizar o banco; não há nova dependência.

Criação, edição, exclusão e substituição de anexo verificam todos os meses fechados atingidos pelo período. Em edições, a verificação considera tanto o funcionário/período original quanto o novo. Afastamentos sem data final são considerados abertos também nessa verificação. A API retorna **409** e informa qual competência precisa ser reaberta.

As operações não alteram `apuracao_fechada`. Consultas de períodos fechados continuam utilizando o snapshot existente. Cadastros de ocorrências e fechamento/reabertura reservam a escrita SQLite antes de validar quando executados em uma nova sessão HTTP, serializando essas operações. A alteração de empresa de um funcionário que já possui histórico de ocorrências é bloqueada para preservar sua vinculação.

## Regras de cadastro

| Tipo | Período permitido |
| --- | --- |
| Atestado | Um ou vários dias integrais; ou horários em um único dia |
| Declaração de horas | Um único dia, obrigatoriamente com os dois horários |
| Férias | Intervalo integral, com início e fim |
| Afastamento | Intervalo integral, com fim opcional |

Data final anterior à inicial é rejeitada. Os horários devem ser locais, informados em conjunto e estritamente crescentes. Períodos parciais não atravessam dias. Funcionário inexistente retorna 404. Campos de atualização são validados junto com os dados já cadastrados, evitando que um PATCH parcial produza um registro inválido.

**Sobreposições:** ocorrências integrais sobrepostas são bloqueadas. Duas ocorrências parciais no mesmo dia são permitidas se não se cruzarem; intervalos adjacentes, como 13:00–14:00 e 14:00–15:00, são aceitos. Não há decisão automática de precedência entre férias, atestado e afastamento.

## Integração com a apuração

### Ocorrências integrais

Férias, afastamento integral e atestado integral retiram a jornada exigida do dia, zeram faltas e atrasos e identificam o tipo no resultado. A jornada prevista da escala é mantida como referência; `jornada_exigida_minutos` representa a exigência após considerar a ocorrência. Não são inventadas batidas para representar abono.

A conferência operacional continua explícita: uma ocorrência não marca automaticamente a marcação como conferida. Se houver batidas em um dia de ocorrência integral, o resultado sinaliza conflito para revisão, sem lançar atraso ou falta.

### Declarações e atestados parciais

O abono automático requer **escala de horário fixo e batidas completas e válidas**. O interpretador calcula os minutos de jornada prevista que não foram trabalhados e que estão cobertos pela ocorrência. Isso exclui almoço, períodos fora da escala e tempo já trabalhado; o abono não aumenta horas trabalhadas nem gera horas extras.

O exemplo solicitado foi testado:

- Escala: 08:00–12:00 / 13:00–17:00.
- Batidas: 08:00–12:00 / 15:00–17:00.
- Declaração: 13:00–15:00.
- Resultado: **360 minutos trabalhados + 120 abonados; atraso zero e extra zero**.

Uma declaração de apenas 13:30–14:30 nesse exemplo abona 60 minutos e mantém 60 minutos de ausência. A tolerância de atraso da escala existente é aplicada ao déficit restante. Precisão de cálculo: minutos, como no motor atual.

Escalas definidas somente por carga horária, batidas incompletas e situação manual incompatível com abono parcial geram pendência `ocorrencia_requer_revisao`. O cadastro é preservado, mas esses casos não são silenciosamente considerados resolvidos.

### Dados entregues ao frontend e aos relatórios

Cada detalhe de dia inclui `ocorrencias`, `ocorrencias_rotulo`, `minutos_abonados` e `jornada_exigida_minutos`, além dos campos já existentes. A Conferência apresenta a ocorrência junto à situação e ao histórico do dia, mantendo a situação editável da marcação separada da interpretação do motor.

O Excel mostra o rótulo processado na coluna de situação. O relatório imprimível inclui uma seção de ocorrências com funcionário, data, tipo e minutos abonados. Essas apresentações apenas consomem o resultado; não contêm regras de apuração.

## Endpoints

| Método e rota | Função |
| --- | --- |
| `GET /ocorrencias` | Listar e filtrar |
| `POST /ocorrencias` | Criar |
| `GET /ocorrencias/{id}` | Consultar registro ativo |
| `PATCH /ocorrencias/{id}` | Editar |
| `DELETE /ocorrencias/{id}` | Excluir logicamente; resposta 204 |
| `GET /ocorrencias/{id}/historico` | Consultar auditoria, inclusive após exclusão |
| `POST /ocorrencias/{id}/anexo` | Anexar/substituir documento por multipart, campo `arquivo` |
| `GET /ocorrencias/{id}/anexo` | Baixar o anexo atual |

Filtros: `empresa_id`, `funcionario_id`, `competencia_id`, `data_inicio`, `data_fim` e `incluir_excluidas`. A seleção de competência define o intervalo mensal; o filtro considera a interseção dos períodos, incluindo afastamentos em aberto.

## Interface

O menu da empresa ganhou **Ocorrências / Afastamentos**, com rota `#/empresas/{id}/ocorrencias`. A tela permite trocar de empresa, selecionar funcionário, filtrar por competência ou datas e incluir registros excluídos na consulta de histórico.

O formulário reutiliza os diálogos existentes e adapta os campos ao tipo. Declaração mostra data e horários; férias mostra início/fim; atestado oferece cobertura integral ou parcial; afastamento permite deixar o fim vazio. Há ações de editar, excluir com confirmação, consultar histórico, anexar e baixar documento. Sem API, a tela explica a indisponibilidade e não simula salvamento de ocorrências.

Na validação visual foi corrigido um comportamento dos estilos existentes que mantinha campos condicionais visíveis. A nova tela também usa identificação de versão nos arquivos estáticos para evitar reaproveitamento de versões antigas pelo cache.

## Anexos e auditoria

Anexos ficam em `uploads/ocorrencias/{id}/`, com nome físico UUID e referência relativa no banco. São aceitas extensões PDF, PNG, JPG e JPEG, até **25 MB**; arquivos vazios são rejeitados. Downloads validam o caminho dentro de uploads e são servidos como arquivo para baixar. Falhas de gravação/transação removem o arquivo recém-criado. Nenhum binário é armazenado no SQLite.

Arquivos substituídos e de ocorrências excluídas são preservados para manter a rastreabilidade. Não há limpeza automática desses documentos, OCR, antivírus nem validação do conteúdo documental.

Criação, alteração, exclusão e anexação registram instante UTC, ator **Operador local** e valores anteriores/posteriores na mesma transação do cadastro. O histórico continua acessível após exclusão. Na interface, os eventos são apresentados com nomes de campos legíveis e horários de São Paulo. Sem autenticação, não existe identificação individual do operador nem proteção contra alteração direta do arquivo SQLite.

## Arquivos

Criados:

- `backend/app/ocorrencias/__init__.py`
- `backend/app/ocorrencias/schemas.py`
- `backend/app/ocorrencias/service.py`
- `backend/app/ocorrencias/interpretacao.py`
- `backend/app/ocorrencias/routes.py`
- `backend/tests/test_ocorrencias.py`
- `frontend/js/ocorrencias.js`
- Este relatório e as evidências em `logs/`.

Alterados:

- `backend/app/database/models.py` e `migrations.py`
- `backend/app/main.py`
- `backend/app/apuracao/service.py`
- `backend/app/competencias/routes.py`
- `backend/app/funcionarios/routes.py`
- `backend/app/relatorios/routes.py`
- `frontend/app.js`, `index.html`, `styles.css`, `js/components.js` e `js/screens.js`
- `README.md`.

A lista de fontes foi comparada com os hashes iniciais: [arquivos-ocorrencias.json](logs/arquivos-ocorrencias.json).

## Cobertura e validação visual

Os 28 novos testes cobrem CRUD dos quatro tipos, filtros por funcionário/período/competência, datas e horários inválidos, funcionário inexistente, intervalos abertos, sobreposição integral/parcial, PATCH com validação conjunta, bloqueios de criação/edição/exclusão/anexo em competência fechada, reabertura, estabilidade de snapshot, abonos integrais e parciais, preservação das batidas, pendências para casos não calculáveis, persistência em outra conexão, auditoria após exclusão, migração idempotente, relatório e anexos inválidos/vazios/acima do limite.

No navegador, usando o banco fictício `logs/validacao-ocorrencias.db`, foram verificados cadastro de declaração, persistência após recarregamento, adaptação do formulário para férias, bloqueio de sobreposição, cadastro de férias sem conflito, edição, exclusão lógica e consulta dos eventos de criação/alteração/exclusão. A inspeção visual levou aos ajustes de campos condicionais e espaçamento dos filtros.

## Aplicação e limites

Antes de utilizar na instalação real, encerre os serviços, preserve um backup conjunto do banco e uploads e reinicie com o código atualizado. A inicialização aplicará o schema 5. Não é necessário instalar novas dependências. O banco de validação fictício não deve substituir o banco operacional.

Pontos para revisão manual:

- Ocorrência parcial sem horário fixo ou com batidas incompletas exige conferência; o módulo não supõe períodos trabalhados.
- Batidas em dia de ocorrência integral exigem revisão da compatibilidade.
- Fechamentos excepcionais com pendências continuam possíveis mediante a confirmação já existente no produto.
- Períodos parciais e jornadas não atravessam a meia-noite nesta implementação. Datas finais de ocorrências integrais são inclusivas.
- O calendário existente materializa dias para funcionários ativos. O cadastro não adiciona regras de admissão/demissão ou um calendário novo para funcionários inativos.
- Anexos preservados consomem espaço em disco; não há política automática de retenção.
- Permanece o aviso de depreciação de `datetime.utcnow()` do código existente, sem falha nos testes.

Não foram incluídos DSR, regras sindicais/previdenciárias, INSS, licença-maternidade específica, banco de horas complexo, autenticação ou calendário de feriados.
