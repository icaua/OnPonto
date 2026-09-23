# Espelho individual e revisão de integração

Data: 08/09/2026. Projeto: On Ponto.

## Entrega

Implementada a rota `GET /relatorios/espelho-ponto?competencia_id=...&funcionario_id=...`, acessível pelo botão **Emitir espelho** na Conferência. Abre em nova aba, usando o mesmo padrão de link do relatório da empresa e o CSS de impressão agora compartilhado.

O documento inclui empresa/CNPJ, funcionário/código/cargo, competência, dias e horários, situação, ocorrências, minutos abonados, totais individuais, observações, pendências e duas assinaturas com data. Os textos cadastrais e observações são escapados. Funcionário ausente da apuração e competência inexistente retornam 404.

A fonte continua sendo `apurar_competencia`: nenhuma apuração paralela ou calendário próprio foi criado. Competências fechadas usam o snapshot. Cargo é consultado no cadastro atual e assim identificado no documento, conforme o pedido; nome e código vêm do resultado preservado. Não houve alteração de schema, entidade, importador ou do arquivo central `apuracao/service.py`.

## Revisão: problemas reproduzidos e corrigidos

| Área | Antes | Depois |
|---|---|---|
| Espelho × salvamento | A emissão abria o relatório mesmo com alterações na fila ou em salvamento, usando dados anteriores aos da tela. | A emissão informa que é necessário concluir **Salvar agora** antes de abrir. Vale também para impressão da empresa. |
| Funcionário × calendário/apuração | Trocar a empresa de um funcionário com marcações retirava seus dias da apuração original e provocava duplicidade ao gerar calendário no destino. | A API retorna 409 enquanto houver histórico de marcações. Transferência sem histórico continua permitida. |
| Ocorrência × tolerâncias | Batidas 08:00–12:00/13:05–17:05, tolerância de intervalo de 10 min: uma declaração 18:00–19:00 criava 5 min de atraso; uma declaração 13:00–13:01 criava 4 min. Antes de qualquer declaração, o atraso era zero. | Ocorrência com abono zero preserva a apuração. Abono efetivo também não pode elevar o atraso previamente apurado. Conflitos com situação manual continuam pendentes. Correção restrita ao interpretador de ocorrências. |
| Conferência × Excel | Jornada completa deslocada em 30 min aparecia com saldo zero na tela e −00:30 no Excel. Dias sem cálculo também podiam mostrar saldo numérico. | A tela usa extras menos atrasos devolvidos pela apuração, como o Excel, e apresenta saldo indisponível quando o cálculo está pendente. |
| Edição × atualização da apuração | Edições de horário e situação nem sempre recarregavam a apuração após salvar. O cálculo local ignorava tolerâncias e podia manter abonos antigos. | Todo salvamento de dia agenda atualização da apuração. Durante a edição online, o saldo aguarda a resposta do motor. |

Cada falha acima foi reproduzida em teste antes da alteração e passou após a correção. Os logs anteriores à correção foram mantidos, inclusive a variante com abono efetivo.

## Cobertura das três áreas solicitadas

1. **Espelho:** revisados funcionário inativo sem marcações, mês inteiro pendente, caracteres HTML/aspas, vários funcionários, totais, ocorrências e fechamento excepcional. Nenhuma falha adicional encontrada nesses casos após a implementação: ausência de dados aparece como indisponível; os motivos de pendência permanecem no documento fechado, embora o banner de revisão seja exclusivo de competências abertas. O risco de emissão antes do salvamento foi corrigido.
2. **Integrações:** corrigidos os problemas de transferência e ocorrência/tolerância. O teste que combina detector TXT, calendário previamente gerado, declaração parcial, reimportação e fechamento passou. Detector/importação × calendário/fechamento: **revisado, nenhuma falha adicional encontrada nos cenários exercitados**. Alterar a escala após fechar não modifica o HTML preservado do espelho.
3. **Rotina de DP:** corrigidas a divergência tela/Excel e a falta de atualização depois de editar. Incluídos testes de emissão em nova aba, modo demonstração, ausência de competência, salvamento pendente e saldo indisponível.

## Ponto encontrado para decisão, sem mudança automática de regra

A aplicação de tolerância de intervalo **ao resíduo depois de um abono efetivo** ainda merece definição explícita. Exemplo reproduzido: intervalo excedente de 12 min, tolerância de 10 min e abono de 3 min resulta hoje em 9 min de atraso. Se a política desejada for reaplicar a tolerância aos 9 min restantes, o resultado esperado seria zero. Esta rodada preservou a regra existente nesse caso; decidiu apenas que uma ocorrência não pode aumentar o atraso anterior. A generalização da regra não foi feita automaticamente, pois alteraria resultados de negócio além da apresentação do espelho. Evidência: `logs/revisao-espelho-decisao-tolerancia.json`.

Funcionários inativos sem registros e snapshots antigos incompletos não recebem dias inventados pelo relatório. Cargo histórico não é recuperável a partir do snapshot atual. Essas limitações são explicitadas sem criar novas entidades ou migrações.

## Evidências

- Antes: **134 testes aprovados** — `logs/testes-espelho-antes.txt`.
- Parte 1, antes da revisão: **140 testes aprovados** — `logs/testes-espelho-parte1.txt`.
- Suíte final: **148 testes aprovados** — `logs/testes-espelho-final.txt`.
- Frontend: **7 testes aprovados** — `logs/testes-espelho-frontend.txt`.
- Sintaxe: `compileall` do backend e `node --check` de `app.js` e `screens.js` passaram.
- HTTP real: 200 para espelho válido, 404 para competência/funcionário inexistentes e 422 sem funcionário — `logs/espelho-http.json`. Após o ajuste final do layout de assinatura, os 14 testes do espelho foram executados novamente e passaram.
- Falhas antes das correções: `logs/revisao-espelho-falhas-backend.txt`, `logs/revisao-espelho-falhas-frontend.txt`, `logs/revisao-espelho-falhas-salvamento.txt` e `logs/revisao-espelho-falha-abono-efetivo.txt`.
- Navegador: conferidos cabeçalho, tabela, totais e assinaturas; o botão real abriu nova aba para competência 1/funcionário 1 no banco fictício. Exemplo estático: [espelho-exemplo.html](logs/espelho-exemplo.html). A impressão física não foi executada.
- Código anterior: `logs/fontes-antes-espelho.zip`; diferenças: `logs/alteracoes-espelho.diff`.

Testes usam bancos isolados. O banco e os uploads reais não foram alterados.

## Arquivos

- `backend/app/relatorios/routes.py`: endpoint individual e estilo compartilhado.
- `backend/app/funcionarios/routes.py`: proteção do histórico de marcações.
- `backend/app/ocorrencias/interpretacao.py`: ocorrência sem aumento indevido de atraso.
- `frontend/app.js`, `frontend/js/screens.js`, `frontend/index.html`: emissão, saldo, atualização após salvar e cache dos assets.
- `backend/tests/test_espelho_ponto.py`: 14 testes novos.
- `frontend/tests/espelho.test.cjs`: 7 testes novos; `frontend/tests/espelho-browser.html`: configuração restrita à origem local de teste.
- `README.md` e este relatório: uso, escopo e evidências.

Para usar no projeto, reinicie a API e recarregue o frontend. Selecione a competência e o funcionário na Conferência, conclua os salvamentos e clique em **Emitir espelho**.
