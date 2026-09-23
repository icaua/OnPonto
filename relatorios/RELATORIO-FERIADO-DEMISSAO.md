# Relatório — horas de feriado e data de demissão

Implementação concluída em 15/09/2026. **239 testes passaram; zero falhas.**

## Demissão

- Campo `data_demissao` opcional, do tipo `Date`, no modelo, schemas, API, formulário e lista de funcionários.
- Schema 8 adiciona a coluna nullable, sem preencher ou converter dados antigos.
- Vínculo considera admissão e demissão, incluindo ambas as datas. Dias automáticos fora desse intervalo não são gerados. Ao editar a data, apenas placeholders vazios e intocados são removidos; batidas e histórico permanecem preservados.
- POST e PATCH rejeitam demissão anterior à admissão. No PATCH, a validação combina o campo recebido com o cadastro existente; omissão preserva e `null` limpa.
- O status continua **Fora do vínculo**. Batidas posteriores recebem **“Marcação posterior à data de demissão”**, sem jornada, atraso, extra ou horas de feriado. O resumo diferencia os motivos anterior à admissão e posterior à demissão.
- A avaliação de competência sem vínculo usa a interseção dos períodos, para contemplar corretamente quem foi admitido e desligado no mesmo mês.

## Horas de feriado

- Feriado passou a ter cálculo próprio, tanto manual quanto aplicado pelo Calendário.
- Sem batidas: trabalho e horas 100% zerados, sem pendência por ausência de trabalho, inclusive quando não há escala.
- Com batidas completas e válidas: duração efetiva registrada em `horas_trabalhadas_minutos` e `horas_feriado_minutos`, com `horas_feriado` formatado. Atraso, extra comum e jornada exigida ficam zerados.
- Batidas parciais ou inválidas: pendência explícita; não se estima duração. O total 100% do funcionário aparece como **Indisponível** enquanto existir feriado incompleto. Um dia normal pendente não invalida, por si só, as horas de feriado completas.
- A rubrica **Horas 100% (feriado)** registra a duração real: quatro horas trabalhadas são `04:00`, sem duplicar minutos nem calcular valores de folha.

## Apresentação e compatibilidade

- Resumo da interface: nova coluna separada das extras comuns.
- Excel: coluna acrescentada ao final das abas **Resumo** e **Marcações**, preservando a posição das colunas anteriores. Usa duração numérica e formato `[h]:mm`, incluindo zero; dados incompletos aparecem como “Indisponível”.
- Espelhos individual e em lote: anotação na célula de status do dia e total adicional quando há horas de feriado. Feriados incompletos mostram aviso de indisponibilidade. Sem esses casos, o layout anterior permanece igual, sem coluna adicional.
- Snapshots antigos sem os campos novos são lidos com valor padrão zero pelos consumidores. Não há recálculo nem regravação do snapshot fechado. Editar demissão também não modifica o fechamento preservado.
- Ocorrências, tolerâncias e importadores não foram alterados.

## Validação

| Suíte | Existentes | Novos | Executados | Passaram | Falharam |
|---|---:|---:|---:|---:|---:|
| Backend | 199 | 17 | 216 | 216 | 0 |
| Frontend | 20 | 3 | 23 | 23 | 0 |
| **Total** | **219** | **20** | **239** | **239** | **0** |

Cobertura nova: limites inclusivos do vínculo, demissão anterior à competência, limpeza da data, preservação de batidas posteriores e de fechamento, validação de PATCH parcial, migração 7 → 8, feriado vazio/completo/parcial, duas e quatro batidas, múltiplos dias/funcionários, Excel numérico, espelhos individual/lote e snapshots antigos.

Os testes anteriores de admissão, feriado, resumo, fechamento, tolerâncias e importação passaram. O teste de contrato do Excel recebeu somente a atualização dos cabeçalhos e do intervalo de filtro para contemplar a nova coluna.

Validação visual com banco fictício separado: demissão carregada no formulário e na lista, Resumo com `04:00` de feriado, e anotação/total no espelho. Sem erros JavaScript capturados nesses fluxos.

Migração executada duas vezes sobre cópia do backup de schema 7: schema final 8, hashes dos dados anteriores preservados, novas demissões nulas, integridade SQLite válida e nenhuma violação de chave estrangeira. A migração do banco utilizado pela aplicação segue a inicialização automática da API.

## Arquivos e evidências

- Banco: `backend/app/database/models.py`, `migrations.py`.
- Cadastro/vínculo: `backend/app/funcionarios/schemas.py`, `routes.py`, `backend/app/calendario/service.py`.
- Cálculo/exportação: `backend/app/apuracao/service.py`, `backend/app/relatorios/routes.py`.
- Interface: `frontend/app.js`, `frontend/js/screens.js`, `frontend/index.html`.
- Testes: `backend/tests/test_demissao_feriado.py`, `test_demissao_api.py`, `test_relatorio_excel.py`, `frontend/tests/demissao-feriado.test.cjs`.
- Resultados: `logs/testes-feriado-demissao-final.txt`, `logs/testes-feriado-demissao-frontend-final.txt`, `logs/migracao8-validacao.json`.
- Backups anteriores às alterações: `backups/feriado-demissao-antes-20260915.zip` e `backups/onponto-antes-schema8-20260915.db`.

Permanecem apenas os avisos de depreciação de `datetime.utcnow()` já existentes; eles não causaram falhas.
