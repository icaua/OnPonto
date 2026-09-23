# Relatório de correções — tolerância e espelhos em lote

Data: 09/09/2026. Projeto: On Ponto.

## Resultado

Implementadas as decisões de produto: tolerância de intervalo opcional que herda a tolerância geral, espelho em A4 retrato e emissão de todos os funcionários pela tela de Exportações. Foram preservados os cálculos de abono parcial e os testes originais do espelho individual.

## 1. Tolerância de intervalo

O modelo e os schemas de criação, atualização e leitura aceitam `tolerancia_intervalo_minutos = null`. O formulário começa vazio e explica a herança. Salvar vazio envia `null`; digitar `0` envia zero. Na atualização, omitir o campo preserva o valor anterior; enviar `null` limpa uma definição anterior.

Em `backend/app/apuracao/service.py`, a única mudança de comportamento é a consulta à pequena função `tolerancia_intervalo_efetiva(escala)` no cálculo de atraso por intervalo: valor explícito, incluindo zero, tem prioridade; `None` usa `tolerancia_atraso_minutos`. A busca no código confirmou que não existe outro leitor direto desse campo para cálculo.

Exemplo testado: escala com almoço de 12:00 a 13:00 e tolerância geral de 10 minutos; batidas de 08:00, 12:00, 13:05 e 17:05. Com intervalo explícito zero, atraso de 5 minutos; com intervalo não especificado, atraso zero. O mesmo caso foi executado antes e depois da migração.

### Migração para schema 6

A migração permite `NULL` na coluna e converte todo zero histórico para `NULL` somente quando a versão anterior é menor que 6. Valores positivos são mantidos. A transação abrange DDL, conversão, verificação de chaves estrangeiras e atualização da versão. Um teste de falha simulada confirmou rollback da estrutura, valores e versão. Uma segunda execução não converte zeros explícitos novos.

**Contagem observada: 1 escala convertida, ID 1**, na cópia de validação do banco atual. A conversão interpreta o zero histórico como “não especificado”, conforme a decisão de produto. Se o responsável confirmar que esse caso precisava de tolerância zero deliberada, deve preencher `0` no cadastro após a atualização.

O banco original `backend/onponto.db` foi consultado somente para leitura e permanece no schema 5. A migração ocorrerá na próxima inicialização da API com este código. A contagem efetiva é registrada no log de inicialização quando houver conversão; poderá diferir se o cadastro mudar antes disso.

A cópia `logs/migracao6-validacao.db` passou por duas execuções: primeira converteu 1 escala; segunda, zero. A comparação de todas as linhas e campos das sete tabelas manteve todos os dados, exceto a conversão prevista: 1 empresa, 1 escala, 1 competência, 1 funcionário, 2 arquivos recebidos, 30 marcações e nenhuma ocorrência. Integridade SQLite: `ok`; violações de chave estrangeira: zero. Snapshots também foram preservados nos testes.

Evidência: [migracao6-validacao.json](logs/migracao6-validacao.json).

## 2. A4 retrato

O documento usa `@page { size:A4 portrait; margin:10mm; }`, com largura útil de 190 mm e altura útil de 277 mm. A tabela conserva as 11 colunas e todos os dados, com fonte de 9,5 px, células de 2 px e proporções de coluna ajustadas. Cabeçalho, totais, notas e assinaturas têm espaçamento compacto. Os dois campos de assinatura e data permanecem.

Foram renderizados HTMLs produzidos pelas próprias rotas, em Chromium. O verificador lê as dimensões reais do DOM, converte pixels em milímetros (`px × 25,4 / 96`) e compara a altura do topo do cabeçalho ao fim do rodapé com os 277 mm disponíveis. O botão de impressão fica fora dessa medição e é ocultado na impressão.

| Cenário renderizado | Dias por funcionário | Notas | Largura útil | Altura de conteúdo | Resultado estimado |
|---|---:|---:|---:|---:|---|
| Individual, julho de 2026 | 31 | 3 | 190 mm | 218,88 mm | Cabe em uma página |
| Lote, 3 funcionários | 31 cada | 3 cada | 190 mm | 218,88 mm cada | Cabe uma página por funcionário |
| Individual com nota extensa | 31 | 4 | 190 mm | 499,08 mm | Requer continuação |

A altura média das linhas foi de 4,34 mm. O cenário comum tem cerca de 58 mm de folga. A nota extensa manteve o marcador final e todos os 13.492 caracteres da seção de notas, sem truncamento. As notas podem continuar e cada funcionário seguinte começa em página nova.

Esta verificação mede o HTML em largura física equivalente à impressão; não constitui contagem de páginas de um PDF gerado. As estimativas consideram escala de impressão de 100%, A4 e margens indicadas. Conteúdos mais longos e configurações do navegador podem alterar a paginação.

Evidências: [medidas-espelhos-retrato.json](logs/medidas-espelhos-retrato.json), [individual de 31 dias](logs/espelho-retrato-31dias.html), [lote de três funcionários](logs/espelhos-lote-31dias.html) e [notas extensas](logs/espelho-retrato-notas-longas.html). São dados fictícios; o medidor foi anexado apenas a essas amostras.

Para reproduzir, execute `.venv\Scripts\python.exe backend/tests/gerar_espelhos_validacao.py` e abra os HTMLs em um navegador com janela de pelo menos 794 px de largura. O JSON de medição aparece abaixo do documento. O script usado é `frontend/tests/medir-espelho.js`.

## 3. Emissão em lote e frontend

Nova rota: `GET /relatorios/espelho-ponto-lote?competencia_id=...`.

As emissões individual e em lote usam `renderizar_bloco_espelho`. A rota em lote chama `apurar_competencia` exatamente uma vez, agrupa os dias por funcionário e usa o resumo retornado como lista de participantes. Os cargos atuais são obtidos em uma consulta conjunta e continuam identificados como cadastro atual. O conteúdo de cada bloco foi comparado literalmente com o bloco individual correspondente.

Cada bloco tem quebra de página após o funcionário, exceto o último. Funcionários presentes no resumo sem dias são incluídos com a mensagem já usada na emissão individual: “Sem marcações disponíveis para este funcionário nesta competência.” Totais indisponíveis não são apresentados como zeros válidos.

Se o resumo estiver vazio, a resposta é HTTP 200 com “Nenhum funcionário disponível nesta competência.” Competência inexistente recebe 404. O teste de fechamento confirmou que mudanças posteriores de escala, nome e código não alteram o lote; funcionário cadastrado depois do fechamento não entra no snapshot preservado.

Na tela **Exportações**, o quarto cartão é **Espelhos de ponto (todos os funcionários)**, com a descrição **Um espelho por funcionário, pronto para impressão e assinatura.** e o botão **Abrir espelhos**. A ação abre nova aba sem parâmetro de funcionário, usando o mesmo mecanismo da emissão individual. Edições pendentes, salvamento em andamento, ausência de competência e modo demonstração impedem a emissão. O botão individual **Emitir espelho** permanece.

## 4. Validação e preservação

| Verificação | Resultado |
|---|---|
| Suíte de backend antes das alterações | 148 testes aprovados |
| Suíte após a etapa de tolerância | 152 testes aprovados |
| Suíte final de backend | **156 testes aprovados**, em 14,729 s |
| Suíte final de frontend | **10 testes aprovados** |
| Testes originais de `test_espelho_ponto.py` | 14 aprovados, arquivo idêntico byte a byte |
| `ocorrencias/interpretacao.py` | Idêntico byte a byte |
| Compilação Python e sintaxe JavaScript alterado | Aprovadas |

Os oito novos testes de backend cobrem herança, zero explícito, schemas, atualização, migração, rollback, equivalência dos blocos, única apuração, ausência de dados, snapshot e preservação de notas. Os três novos testes de frontend cobrem o lote, o quarto cartão e os payloads de cadastro/edição da tolerância. Os demais testes existentes mantiveram suas verificações; apenas expectativas de migração foram atualizadas para a nova versão e para o zero histórico convertido.

Permanecem avisos de depreciação de `datetime.utcnow()` em código preexistente; não houve falha de teste associada.

Logs: [backend](logs/testes-retrato-lote-final.txt), [frontend](logs/testes-retrato-lote-frontend.txt), [hashes dos arquivos preservados](logs/arquivos-preservados-retrato-lote.json). Comparação dos fontes anteriores: [alteracoes-retrato-lote.diff](logs/alteracoes-retrato-lote.diff); cópia anterior dos arquivos desta rodada: `logs/fontes-antes-retrato-lote.zip`.

## Uso da atualização

Reinicie a API para registrar a nova rota e executar a migração de schema 6, preservando o backup habitual do banco e uploads. Recarregue o frontend; a versão dos scripts no HTML foi atualizada para evitar cache antigo. Revise o cadastro da escala ID 1 caso precise manter tolerância de intervalo explicitamente zero.
