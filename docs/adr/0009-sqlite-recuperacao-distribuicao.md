# 0009 — SQLite, recuperação e distribuição reproduzível

Data: 2026-10-10. Estado: aceito.

Schema 19 acrescenta dois índices após EXPLAIN e medição: marcações `(competencia_id,arquivo_origem_id)` cobre DISTINCT de origem; vínculos `(funcionario_id,vigente_desde DESC,id DESC,vigente_ate)` evita ordenação na consulta por vigência. O candidato `(competencia_id,data,funcionario_id)` foi rejeitado: eliminou sort, mas aumentou leitura local 101,7→147,2 ms por acessos à tabela. Ledger não recebeu índice novo porque não mostrou ganho no cenário avaliado. Nenhum índice legado foi removido.

Com 1.000 funcionários/61.000 marcações e 25 arquivos: consulta de origem 10,375→0,054 ms; vigência 0,0535→0,0436 ms. DB 135.380.992→136.409.088 bytes, acréscimo 0,76%. São medianas de sete SELECTs locais, sem tracing. Três cenários novos de importação/fechamento com 1.000 pessoas e um dia elegível: confirmação 1.453,807→1.468,710 ms; fechamento 440,769→440,493 ms. Há pequeno custo de escrita; não se promete ganho em todas as operações. Evidências JSON em docs/benchmarks.

Busy timeout explícito de dez segundos, FK por conexão, optimize limitado após commit de migração. SQLite observado 3.53.1. WAL foi testado com dois escritores e leitor, backup API e restore; não é imposto à instalação. A restrição a disco local e escritores parados para copiar DB+uploads permanece. [SQLite: optimize](https://www.sqlite.org/lang_analyze.html), [WAL/concorrência](https://www.sqlite.org/wal.html).

Conjunto v2 valida integridade/FK, hash do DB e de todos os arquivos e referências conhecidas; falha antes de copiar quando falta evidência ou diverge hash conhecido. Restore exige destino inexistente. Somente caminho operacional de ArquivoRecebido é remapeado na cópia; DocumentoEvidencia, batidas, auditoria, versões, snapshots e ledger são preservados. `restauracao.json` traduz referências históricas sem alterá-las e registra hashes anterior/posterior. Arquivos não referenciados também são incluídos, sem exclusão automática. V1 é compatível com backup histórico sem remapeamento; deve-se gerar v2 para portabilidade de caminhos.

Dependências diretas/transitivas fixadas na distribuição offline existente. Instalador não recorre mais a faixas sem limite superior de versão efetiva. Wheels e binário Python permanecem em Git com SHA256SUMS. Reinstalação offline da venv de teste e pip check passaram; diferenças prévias entre metadata e módulo SQLAlchemy foram eliminadas. Testes subsequentes usam SQLAlchemy 2.0.52/Pydantic 2.13.4/Uvicorn 0.52.3. Windows executado, Linux coberto por CI/configuração, sem afirmar execução remota.

Rollback: não apagar DB ou tabelas; índices são aditivos e reversíveis. Restaurar um conjunto em destino novo, configurar DB/uploads dessa cópia e validar antes de substituir qualquer instalação. Não fazer downgrade sobre novas evidências. Nenhuma migração/instalação em dados reais foi executada.
