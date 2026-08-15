# Checklist de congelamento do MVP — On Ponto

**Versão:** `1.0.0-rc.1`

**Data do congelamento:** 15/08/2026

**Estado:** candidato a MVP, com o fluxo TXT principal homologado.

## Aceite funcional

- [x] Identidade aplicada
- [x] Cadastros reais
- [x] TXT real
- [x] Prévia real
- [x] Conferência persistida
- [x] Batidas originais imutáveis
- [x] Resumo real
- [x] Excel real
- [x] Fechamento
- [x] Launcher Windows/Linux
- [x] Seed demo
- [x] Teste ponta a ponta
- [x] Documentação
- [x] Zero regressões críticas conhecidas

O caminho homologado é:

```text
Empresa
→ Competência
→ Importação
→ Análise
→ Conferência
→ Ajuste
→ Confirmação
→ Persistência
→ Resumo
→ Exportação
→ Fechamento
```

## Evidências do congelamento

- suíte Python completa: 39 testes aprovados;
- parser e fluxo TXT: 22 testes aprovados;
- jornada E2E final em navegador real: 55 verificações aprovadas;
- auditoria E2E independente em navegador real: 52 verificações aprovadas, sem resposta 4xx/5xx inesperada e sem erro JavaScript;
- Excel baixado pela interface, reaberto com `openpyxl` e validado nas abas `Resumo` e `Marcações`;
- importação, edição, autosave, `Ctrl+Z`, troca de funcionário/competência, fechamento, recarga e modo somente leitura validados;
- funcionário desconhecido, data fora da competência, 2, 3 e mais de 4 batidas, reimportação e batida bruta repetida validados;
- instalador e inicializador Linux exercitados em cópias e banco temporários;
- launchers Windows revisados estaticamente, com caminhos independentes do diretório atual, CRLF e dependências locais;
- banco e uploads de desenvolvimento não foram usados de forma destrutiva nos testes.

## Política de congelamento

A partir deste candidato, entram somente:

- correções de bugs;
- pequenos ajustes de UX e acessibilidade;
- correções de texto;
- testes de regressão;
- documentação.

Não entram novas funcionalidades antes da decisão sobre a versão seguinte.

## Fora do escopo desta versão

- XLS legado e novos formatos XLSX de importação;
- OCR e PDF escaneado;
- IA;
- leitura automática de atestado;
- autenticação;
- permissões avançadas;
- motor completo de regras trabalhistas.

Código experimental anterior de importação XLSX/OCR não faz parte do caminho homologado e não representa suporte de produto neste MVP.

## Limitações e riscos conhecidos

- os arquivos `.bat` foram revisados estaticamente, mas não puderam ser executados em Windows 10/11 neste ambiente Linux; a validação final em uma máquina Windows continua sendo um gate de distribuição;
- o produto é local, ligado a `127.0.0.1`, sem autenticação ou perfis de permissão nesta versão;
- o modo offline do frontend usa dados fictícios e não persiste; a demonstração reproduzível do fluxo real usa a API e `seed_demo.py`;
- a reabertura preserva marcações e arquivos, mas limpa a data do fechamento corrente; não existe uma trilha persistente e detalhada de alterações ou de múltiplos eventos de fechamento;
- nomes cadastrais atuais são usados nos relatórios históricos, sem snapshot por competência;
- preferências visuais da Conferência valem apenas durante a sessão do navegador;
- a suíte emite avisos não bloqueantes sobre `datetime.utcnow()` do SQLAlchemy e streams de subprocessos em testes antigos; não há falha associada;
- não há bug crítico de produto conhecido após o E2E final.

## Reproduzir a demonstração

1. Execute o instalador e o inicializador da raiz conforme o [README](README.md).
2. Rode `seed_demo.py` com o Python da `.venv`.
3. Abra `Empresa Demonstração → 07/2026 → Importações`.
4. Analise `backend/tests/fixtures/relogio_ficticio.txt`.
5. Confirme o registro válido, revise a Conferência, exporte o Excel e feche a competência.

O arquivo de exemplo e todos os cadastros do seed são fictícios. `X999` permanece deliberadamente sem cadastro para demonstrar uma divergência visível.
