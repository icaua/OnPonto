# Recuperação e distribuição local

Requisitos fixados em backend/requirements.txt e setup/constraints.txt; Windows offline usa setup/wheels e SHA256SUMS, Linux usa as mesmas versões via internet. Execute instalar_onponto.bat / instalar_onponto.sh. Não há fallback para versões não homologadas. CI Windows/Linux roda as suites; esta execução ocorreu em Windows, Python 3.12.14/SQLite 3.53.1.

Para criar conjunto completo, pare a API e todos os escritores. Exemplos abaixo são parâmetros a substituir; destino deve ser novo, fora dos uploads. Backups automáticos de startup só incluem SQLite; a recuperação portátil inclui também anexos e originais.

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.database.recuperacao backup --banco C:\instalacao\backend\onponto.db --uploads C:\instalacao\backend\uploads --backend C:\instalacao\backend --destino C:\copias\conjunto-novo --offline
..\.venv\Scripts\python.exe -m app.database.recuperacao restore --origem C:\copias\conjunto-novo --destino C:\recuperado\instalacao-nova
```

No Linux use ../.venv/bin/python e caminhos locais. Depois do restore, configure ONPONTO_DATABASE_URL=sqlite:///CAMINHO/onponto.db e ONPONTO_UPLOADS_DIR=CAMINHO/uploads; preserve restauracao.json na pasta do conjunto. O startup aplica migração compatível e verifica FK/integridade. Rode o inventário somente leitura antes de usar:

```text
python -m app.evidencias.inventario --banco CAMINHO/onponto.db --uploads CAMINHO/uploads --backend CAMINHO
```

Hash desconhecido legado é reportado como desconhecido; hash observado no conjunto garante a cópia, sem inventar hash histórico. Ausência/divergência conhecida interrompe backup. Não remover originais, arquivos órfãos ou conjuntos antigos automaticamente. Copie para mídia local protegida; restauração não sobrescreve origem nem destino existente. SQLite mantém journal da instalação; WAL não é ativado automaticamente. Para conjunto antigo v1 com caminhos absolutos, gere v2 a partir da instalação original antes de mover.
