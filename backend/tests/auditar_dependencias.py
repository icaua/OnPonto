"""Consulta pública OSV somente com nomes/versões fixadas, sem dados do escritório."""
import json,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
raiz=Path(__file__).resolve().parents[2]
pacotes=[linha.strip().split('==') for linha in (raiz/'setup/constraints.txt').read_text().splitlines() if linha.strip() and not linha.startswith('#')]
consulta={'queries':[{'package':{'name':nome,'ecosystem':'PyPI'},'version':versao} for nome,versao in pacotes]}
with urlopen(Request('https://api.osv.dev/v1/querybatch',data=json.dumps(consulta).encode(),headers={'Content-Type':'application/json'},method='POST'),timeout=30) as resposta:resultado=json.load(resposta)
if len(resultado['results'])!=len(pacotes):raise RuntimeError('Resposta OSV incompleta.')
ocorrencias=[]
for (nome,versao),resposta in zip(pacotes,resultado['results']):
    ocorrencias.append({'pacote':nome,'versao':versao,'advisories':[v['id'] for v in resposta.get('vulns',[])]})
advisories={}
for id in sorted({id for item in ocorrencias for id in item['advisories']}):
    with urlopen('https://api.osv.dev/v1/vulns/'+id,timeout=30) as r:advisories[id]=json.load(r)
registro={'consultado_em_utc':datetime.now(timezone.utc).isoformat(),'fonte':'https://api.osv.dev/v1/querybatch','escopo':'25 dependências fixadas em setup/constraints.txt; ausência de advisory não certifica segurança. Nenhum arquivo/nome de empregado enviado.','pacotes':ocorrencias,'advisories':advisories}
destino=raiz/'docs/seguranca/dependencias-osv.json';destino.parent.mkdir(parents=True,exist_ok=True);destino.write_text(json.dumps(registro,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'pacotes':len(pacotes),'advisories':len(advisories),'registro':str(destino)}))
