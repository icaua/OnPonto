# Medições reproduzíveis

```powershell
.\.venv\Scripts\python.exe backend/tests/benchmark_http.py --output docs/benchmarks/00-baseline.json
```

O comando cria um diretório temporário para cada porte, inicia API em loopback com DB/uploads isolados, mede requisições HTTP reais e encerra o servidor antes de remover apenas seus próprios dados fictícios. Nunca lê o banco instalado. Nenhum dado de cliente entra nos resultados. A instrumentação está exclusivamente no harness de teste.

Cenário v1: 50, 250 e 1.000 pessoas; duas competências, setembro (30 dias, com bordas/pêndencias) e outubro (31 dias, fechável); três escalas, sábado independente, feriado fictício, política mista com adicional fictício explícito, atraso/extra, ausência/ocorrência integral e parcial, duas/três/cinco batidas e descarte justificado. Fechamento/reabertura, Excel, consulta de saldo e extrato são medidos. Testes de importação existentes complementam conflitos de arquivos TXT/XLSX e identidade.

SQL contado por `before_cursor_execute`, incluindo consultas, escritas e comandos de transação. Latência é de uma requisição inteira com download em loopback. `pico_python_incremental_bytes` é o pico de alocações rastreadas pelo tracemalloc durante o handler menos a ocupação inicial; **não é RSS** nem memória nativa de SQLite. O tracing acrescenta custo e permanece ativo em todas as comparações. GET é repetido três vezes; operações de mutação têm uma amostra por cenário. Não inferir percentis de produção dessas amostras.

Golden master: `backend/tests/fixtures/golden_baseline.json`. Saídas estruturadas da apuração, snapshot, ledger/estornos/compensações e valores das planilhas; timestamps voláteis excluídos. Só regenerar deliberadamente após justificar divergência; testes normais jamais atualizam a referência.

Recuperação do conjunto: `database/recuperacao.py`, testada com DB/schema antigo e arquivos fictícios. Exige escritores parados, verifica hashes/FK/integridade e restaura apenas em **diretório inexistente**. É uma primitiva de recuperação; não substitui automaticamente os backups diários nem remapeia caminhos absolutos de anexos. A integração operacional e o remapeamento de caminhos em recuperação para outra instalação pertencem ao pacote 08.

Pacote 05 acrescenta medições de resumo sem dias, triagem, dias de uma pessoa e PATCH subsequente após o primeiro sincronizar o cache. O PATCH original continua na tabela comparável. O novo PATCH usa alteração adicional de um minuto dentro da mesma tolerância, sem mudar resultados financeiros do cenário. DB inclui cache operacional e uma auditoria adicional; ocupação não é comparação de armazenamento idêntico. `05-triagem-lotes.json` registra implementação intermediária, antes de remover varreduras repetidas no Excel. `05-final.json` registra a implementação estabilizada; hash SHA-256 do código backend é verificado entre cenários. Se código mudar durante uma medição, o harness exige repetição. Referência histórica e golden permanecem os mesmos.
