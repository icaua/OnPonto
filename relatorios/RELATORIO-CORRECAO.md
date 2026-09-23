# Relatório de correção — On Ponto

Data: 07/09/2026  
Resultado: correções implementadas e validadas; 106 testes aprovados.  
Ambiente: Windows, Python da virtualenv do projeto e Node.js disponível localmente.

## 1. Escopo

Foram corrigidos os quatro problemas prioritários da avaliação: alterações indevidas em competências fechadas, recálculo histórico com escalas atuais, aceitação de horários sobrepostos e ausência de persistência do histórico de edições. Também foram corrigidos problemas de liberação de recursos nos testes do Windows e atualizada a documentação de suporte a XLSX.

O código e a documentação foram atualizados nesta pasta. O banco operacional e os uploads não foram alterados nesta execução; a migração foi ensaiada em uma cópia temporária. Nenhum serviço da instalação foi reiniciado.

## 2. Correções

### 2.1 Consultas não modificam competências fechadas

**Antes:** a consulta de apuração gerava dias de calendário mesmo com a competência fechada. A reprodução isolada passou de 1 para 31 marcações.

**Depois:** a geração de calendário retorna sem alterações para competências fechadas. A apuração dessas competências utiliza o resultado preservado no fechamento. Consultas e exportações não incorporam novos funcionários ou dias ao período encerrado.

Arquivos principais: `backend/app/apuracao/service.py`, `backend/app/competencias/routes.py`.

### 2.2 Resultado do fechamento preservado

**Antes:** mudar a carga da escala de 8 para 6 horas alterava um dia fechado de 0 para 120 minutos extras.

**Depois:** o fechamento grava a apuração completa em `competencias.apuracao_fechada`, na mesma transação que altera o status. Consultas e relatórios Excel/impressão utilizam essa cópia. Alterações posteriores de escala, nome ou cadastro de funcionários não recalculam o fechamento.

A reabertura explícita remove a cópia e permite recalcular com as regras atuais. Um novo fechamento grava um novo resultado.

Para competências antigas, a inicialização preserva o resultado disponível naquele momento, sem criar calendário, e identifica a origem dessa preservação no campo `preservacao` da resposta. Essa etapa é idempotente.

Arquivos principais: `backend/app/competencias/preservacao.py`, `backend/app/competencias/routes.py`, `backend/app/database/models.py`, `backend/app/database/migrations.py`, `backend/app/main.py`.

### 2.3 Validação cronológica de horários

**Antes:** `08:00 → 12:00 → 11:00 → 17:00` produzia 600 minutos trabalhados sem erro.

**Depois:** o motor devolve pendência para sequência fora de ordem ou horários iguais. A API de criação e edição rejeita essas sequências com HTTP 422. Em uma edição parcial, a validação considera os horários já existentes e os novos valores em conjunto.

Dias incompletos continuam podendo ser registrados para conferência. Marcações inválidas antigas não são corrigidas automaticamente nem recebem horas inventadas. Jornadas que atravessam a meia-noite continuam fora do cálculo atual.

Arquivos principais: `backend/app/apuracao/service.py`, `backend/app/marcacoes/auditoria.py`, `backend/app/marcacoes/routes.py`.

### 2.4 Histórico persistente de edições

**Antes:** o histórico de edição era mantido apenas em memória no frontend.

**Depois:** criações e alterações pelas rotas POST/PATCH de marcações registram identificador, instante em UTC, ator local, campos alterados e valores anteriores/posteriores. Os eventos são armazenados em `marcacoes_ponto.historico_json`, na mesma transação da alteração, e retornados em `historico` nas consultas da API.

O frontend utiliza o histórico confirmado pelo servidor e o recarrega com a marcação. Reenviar os mesmos valores não duplica eventos. Alterações recusadas não geram eventos persistidos. O histórico não pode ser sobrescrito pelo PATCH. As batidas originais permanecem preservadas.

Arquivos principais: `backend/app/marcacoes/auditoria.py`, `backend/app/marcacoes/routes.py`, `backend/app/marcacoes/schemas.py`, `backend/app/database/models.py`, `frontend/app.js`, `frontend/js/components.js`.

### 2.5 Testes no Windows

Conexões abertas com `sqlite3.connect()` agora são explicitamente fechadas com `contextlib.closing`: o gerenciador de transação SQLite, isoladamente, não fecha a conexão. Pipes de subprocessos também são fechados, e a limpeza é registrada para ocorrer mesmo quando a preparação do teste falha.

Para bloqueios transitórios de arquivo após o encerramento do processo no Windows, a limpeza repete somente erros WinError 32, com limite de 20 tentativas e intervalo de 100 ms. Erros persistentes e outros tipos de erro continuam fazendo o teste falhar.

Arquivos: testes de cadastros, migração, seed, importação, fechamento e relatório; novo `backend/tests/test_support.py`.

## 3. Evidências de validação

| Verificação | Resultado |
| --- | --- |
| Suíte completa após as correções | 106 testes, 0 falhas, 0 erros; 10,773 segundos |
| Novos testes de regressão | 10 cenários adicionais, incluindo uma validação HTTP de histórico e PATCH inválido |
| Migração sobre cópia do banco existente | Schema 4 aplicado duas vezes; contagens de empresas, funcionários, competências, marcações e arquivos preservadas |
| Integridade da cópia migrada | `PRAGMA integrity_check`: `ok`; `PRAGMA foreign_key_check`: nenhuma violação |
| Compilação Python | `compileall` concluído sem erro |
| Sintaxe JavaScript | `node --check` aprovado para app.js, components.js e screens.js |

Comando da suíte:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

Saída integral: [logs/testes-correcao.txt](logs/testes-correcao.txt).

Os novos testes estão em `backend/tests/test_integridade_correcao.py` e `backend/tests/test_cadastros_api.py`. Cobrem leitura de fechamento legado, estabilidade frente a escala/cadastro, reabertura e novo fechamento, preservação legada idempotente, horários sobrepostos/iguais, PATCH parcial, persistência de auditoria em outra sessão, reenvio sem duplicação e bloqueio de edição após fechamento.

Permanece um aviso de depreciação de `datetime.utcnow()` no código existente. Ele não causou falha na suíte. Não foi realizada validação visual ou automação de navegador nesta correção.

## 4. Aplicação na instalação

1. Encerre o On Ponto antes de atualizar a instalação em uso.
2. Preserve uma cópia conjunta de `backend/onponto.db` e `backend/uploads/`.
3. Inicie a aplicação com o código atualizado pelo inicializador habitual.
4. A API adicionará os campos do schema 4 e preservará as competências antigas já fechadas.
5. Confira um período fechado e uma edição de marcação antes de retomar o uso habitual.

Não há nova dependência para instalar. Para reversão operacional, restaure conjuntamente a versão anterior do código e o backup correspondente do banco e dos uploads; não dependa de uma migração reversa automática.

## 5. Limites e trabalho futuro

- A preservação de períodos antigos não recupera regras ou resultados que já tenham sido alterados antes desta atualização. Esses períodos exigem conferência caso haja dúvida sobre os valores disponíveis.
- O histórico passa a existir para as criações/edições pelas rotas de marcação a partir desta atualização. Não reconstitui eventos antigos e não constitui uma auditoria geral de importações, cadastros, escalas ou ações de fechamento.
- Sem autenticação, o ator registrado é “Operador local”; não há identificação individual nem proteção contra edição direta do arquivo SQLite.
- Autenticação, backup automático e uma suíte de navegador não foram adicionados. O uso previsto continua local e individual.
- A divisão do frontend em módulos menores e o travamento completo de versões de dependências permanecem melhorias futuras. A correção não incluiu uma reestruturação ampla da aplicação.

## 6. Complemento — logo e seleção de arquivos no frontend

Correção adicional de 07/09/2026, após relato de problemas na interface.

- **Logo:** a barra lateral usava um SVG incompleto, sem o dimensionamento e os estilos necessários. Agora utiliza os arquivos oficiais `brand/on-ponto-logo-white.svg` no menu expandido e `brand/on-ponto-symbol-white.svg` no menu recolhido, com dimensões explícitas e texto alternativo.
- **Escolher arquivo:** o manipulador geral de cliques encontrava a ação `analyze-import` no formulário pai e cancelava o comportamento nativo do rótulo do input. Ações de formulário agora ficam a cargo do evento de envio; o clique no rótulo volta a abrir o seletor. “Escolher arquivo” e “Trocar arquivo” também são botões reais, acionáveis por teclado, que abrem o input correspondente e respeitam seu estado desabilitado.
- **Cache:** os links dos arquivos CSS e JavaScript alterados receberam uma identificação de versão no HTML, para carregar a correção ao atualizar a página.

Arquivos alterados nesta etapa: `frontend/index.html`, `frontend/styles.css`, `frontend/js/components.js` e `frontend/app.js`.

**Validação desta etapa:** inspeção visual no navegador da logo expandida e do símbolo recolhido; abertura do seletor pelo botão e seleção de `relogio_ficticio.txt`; troca por `relogio_id_tempo_maquina.txt` usando Enter; nova seleção pelo clique na área do nome do arquivo. O nome selecionado apareceu corretamente na interface em todos os casos. `node --check` passou para os JavaScripts alterados.

Os testes de navegador foram realizados no modo demonstração, usando apenas fixtures fictícias do projeto e sem enviar arquivos para o backend. O código de drag and drop não foi alterado. A suíte de backend citada anteriormente não foi reexecutada nesta etapa, que modificou apenas o frontend.
