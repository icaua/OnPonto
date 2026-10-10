import json,statistics
from pathlib import Path
from benchmark_importacao import medir
resultado={'metodo':'3 cenários novos por configuração; 1.000 funcionários com um dia elegível/quatro batidas; versões offline fixadas; índices criados antes dos dados; sem tracing. Resultados locais, sem percentis de produção.','sem_indices':[],'com_indices':[]}
for _ in range(3):
    resultado['sem_indices'].append(medir(1000,sem_indices=True,medir_fechamento=True))
    resultado['com_indices'].append(medir(1000,medir_fechamento=True))
resultado['medianas']={k:{operacao:statistics.median(r[operacao]['ms'] for r in resultado[k]) for operacao in ('analise','confirmacao','fechamento')} for k in ('sem_indices','com_indices')}
Path('docs/benchmarks/08-custo-indices.json').write_text(json.dumps(resultado,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(resultado['medianas']))
