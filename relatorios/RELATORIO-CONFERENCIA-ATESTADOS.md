# On Ponto — Correções da Conferência e cadastro de atestados

Data: 20/09/2026.

## Resultado

A Conferência preserva a rolagem da tabela e do painel de detalhes durante suas atualizações. Quando o dia selecionado sai do filtro, a seleção avança para o próximo dia cronológico; sem próximo, volta ao anterior imediato.

“Adicionar atestado” abre o formulário existente de Ocorrências, preenchido com funcionário, tipo ATESTADO, cobertura integral e datas do dia selecionado. É possível mudar para parcial e informar horários e observação, inclusive em dias com batidas. O cadastro usa a API real, fecha o modal e busca novamente a apuração e as marcações.

## Arquivos alterados

| Arquivo | Motivo |
| --- | --- |
| `frontend/app.js` | Capturar/restaurar `scrollTop` e `scrollLeft` de `.attendance-table-wrap` e `.review-context` no render genérico; escolher próximo/anterior cronológico; conectar a ação ao cadastro real; salvar edições pendentes antes do POST; recarregar a competência após o fechamento do formulário; tratar falha posterior ao salvamento sem oferecer novo POST. |
| `frontend/js/ocorrencias.js` | Expor criação com valores iniciais e callbacks opcionais, reutilizando integralmente formulário, validação, payload e API existentes. Preservar criação/edição e recarga da tela de Ocorrências. |
| `frontend/js/components.js` | Disponibilizar o botão também com batidas; mostrar ocorrência e minutos abonados no painel principal, usando o texto e estilo já existentes no painel alternativo. |
| `frontend/js/screens.js` | Manter o botão do painel alternativo coerente com o principal. |
| `frontend/index.html` | Atualizar as versões dos quatro scripts alterados para evitar cache antigo. |
| `frontend/tests/conferencia-contexto.test.cjs` | Acrescentar 12 testes de regressão de seleção, rolagem, cadastro integral/parcial, bloqueios, integração, tratamento de falhas e compatibilidade da tela de Ocorrências. |

Não houve mudança no CSS, esquema do banco, backend ou regras de cálculo. Este relatório e os logs de validação complementam a entrega.

## Antes e depois

| Situação | Antes | Agora |
| --- | --- | --- |
| Atualizar a Conferência | A recriação dos elementos zerava o scroll. | As posições vertical e horizontal são reaplicadas ao novo DOM. |
| Confirmar dia no filtro Não conferidos | A seleção voltava ao primeiro disponível. | Seleciona próximo cronológico, anterior imediato ou primeiro como último recurso. |
| Trocar funcionário, competência, empresa ou filtro | Sem distinção para preservação de scroll. | A chave de contexto impede transportar a posição de outro contexto; o novo começa na posição inicial. |
| Adicionar atestado | Mudava somente a situação manual da marcação. | Cadastra uma ocorrência persistida e consulta o resultado do backend. |
| Dia com batidas | O botão não era oferecido. | Permite abrir o mesmo formulário e selecionar cobertura parcial. |
| Cadastro salvo seguido de falha na recarga | Não havia esse fluxo. | Informa que o registro foi salvo e que a tela não pôde ser atualizada; o formulário de criação permanece fechado. |

Os bloqueios atuais continuam válidos: competência fechada não permite a ação; dia conferido exige reabertura; cadastro real exige API online. O backend mantém a validação de sobreposição, campos e períodos fechados. A edição manual de situação e seus atalhos existentes não foram alterados.

## Validação

- Backend: **216 testes aprovados**, via `.venv/Scripts/python.exe -m unittest discover -s backend/tests`. Log: `logs/testes-conferencia-backend.txt`.
- Frontend: **35 testes aprovados**, via `node --test frontend/tests/*.test.cjs`. Log: `logs/testes-conferencia-frontend.txt`.
- Sintaxe dos quatro scripts validada com `node --check`.
- Navegador integrado, API e SQLite isolados, com funcionários fictícios. Banco de QA: `logs/conferencia-qa-20260920.db`. O banco de uso normal não foi utilizado na validação manual.
- Dia 20: confirmação manteve `scrollTop = 650` e o mesmo dia selecionado.
- Não conferidos, dia 18: confirmação removeu o dia da tabela, selecionou o dia 19 e manteve `scrollTop = 566`.
- Integral, dia 21: formulário preenchido corretamente; ocorrência persistida; modal fechado; mesmo funcionário, competência, filtro e posição (`scrollTop = 608`, painel em 241). Backend retornou 480 minutos abonados e jornada exigida zero.
- Parcial, dia 22 com batidas 09h–12h: formulário aceitou 13h–18h; ocorrência persistida; backend retornou 300 minutos abonados, 180 trabalhados e 180 exigidos. Painel exibe o abono retornado.
- Edição do dia 23: permaneceu próxima da posição anterior (768 para 776 px, pequena diferença durante a edição da célula). Confirmação preservou scroll vertical em 776 e horizontal em 340.
- Troca para outro funcionário: tabela e painel voltaram a zero e selecionaram o primeiro dia, sem herdar a posição anterior.
- Inspeção visual confirmou a manutenção do layout e identidade atuais. Nenhum erro de console foi capturado nos cenários verificados.

## Pontos de atenção

1. A preservação vale para os renders da sessão, não para um recarregamento completo do navegador. Reduções da lista ou do conteúdo do painel podem limitar a posição ao novo tamanho disponível.
2. Se o registro for salvo e a recarga falhar, recarregue a Conferência para consultar o resultado. Não cadastre novamente a mesma ocorrência.
3. Com escala fixa de quatro horários e apenas entrada às 09h/saída às 12h, o motor atual calcula o abono parcial de 300 minutos, mas mantém a pendência **“As batidas não permitem conferir o horário fixo.”** Isso foi constatado na API e na interface e preservado conforme o escopo, que proíbe alterações de cálculo. O cadastro de atestado não remove automaticamente essa pendência anterior.
4. A situação manual original continua separada da ocorrência. Assim, pode aparecer “Normal” acompanhado de “ATESTADO”; o painel informa os minutos abonados, e o resultado efetivo vem da API.

Não ficaram correções pendentes dentro do escopo solicitado. Os pontos acima descrevem limites e regras preservadas.
