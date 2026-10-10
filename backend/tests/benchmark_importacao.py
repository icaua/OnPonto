"""Medição local sintética de importação; sem acessar instalação real."""
import json
import sys
from datetime import date
from io import BytesIO
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from fastapi import UploadFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_support import TemporaryDirectory
from app.database.session import Base
from app.database.models import Empresa, Escala, Funcionario, Competencia, BatidaOriginal, MarcacaoPonto
from app.importadores import routes
from app.importadores.schemas import ConfirmacaoImportacao

def medir(n):
    with TemporaryDirectory(prefix='onponto-bench-import-ficticio-') as pasta:
        raiz=Path(pasta); engine=create_engine(f"sqlite:///{raiz/'ficticio.db'}")
        try:
            Base.metadata.create_all(engine)
            with Session(engine) as db, patch.object(routes,'UPLOADS_DIR',raiz/'uploads'):
                e=Empresa(nome='Empresa Fictícia Benchmark Importação');db.add(e);db.flush()
                escala=Escala(empresa_id=e.id,nome='Fictícia',jornada_seg_sex_horas=8);db.add(escala);db.flush()
                c=Competencia(empresa_id=e.id,mes=9,ano=2026);db.add(c)
                db.add_all(Funcionario(empresa_id=e.id,escala_id=escala.id,codigo=f'F{i:04d}',nome=f'Pessoa Fictícia {i}',
                    data_admissao=date(2026,9,1),data_demissao=date(2026,9,1)) for i in range(n));db.commit()
                conteudo=('ID\tNome\tTempo\n'+''.join(f'F{i:04d}\tPessoa Fictícia {i}\t01/09/2026 {h}:00\n'
                    for i in range(n) for h in ('08:00','12:00','13:00','17:00'))).encode()
                contagem=[]
                def contar(*args): contagem.append(args[2].split(None,1)[0].upper())
                event.listen(engine,'before_cursor_execute',contar)
                inicio=perf_counter(); previa=routes.analisar_importacao(c.id,e.id,9,2026,
                    UploadFile(filename='ficticio.txt',file=BytesIO(conteudo)),db)
                analise={'ms':round((perf_counter()-inicio)*1000,3),'sql':len(contagem)};contagem.clear()
                p=ConfirmacaoImportacao(empresa_id=e.id,competencia_id=c.id,arquivo_id=previa['arquivo']['id'],
                    revisao_previa=previa['revisao_previa'],registros_ids=[i['id'] for i in previa['preview']])
                inicio=perf_counter(); r=routes.confirmar_importacao(p,db)
                confirmar={'ms':round((perf_counter()-inicio)*1000,3),'sql':len(contagem),'select':contagem.count('SELECT')};contagem.clear()
                inicio=perf_counter(); repetida=routes.confirmar_importacao(p,db)
                repetir={'ms':round((perf_counter()-inicio)*1000,3),'sql':len(contagem)}
                assert r['total_importados']==n and repetida['idempotente']
                assert db.query(BatidaOriginal).count()==n*4 and db.query(MarcacaoPonto).count()==n
                return {'funcionarios':n,'batidas':n*4,'analise':analise,'confirmacao':confirmar,'reenvio':repetir,
                    'db_bytes':(raiz/'ficticio.db').stat().st_size}
        finally: engine.dispose()

if __name__=='__main__':
    resultado={'metodo':'Caso de uso local, tempo sem tracemalloc; SQL inclui escritas. Banco e arquivos fictícios temporários.',
        'cenarios':[medir(n) for n in (50,250,1000)]}
    Path(sys.argv[1]).write_text(json.dumps(resultado,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(resultado,ensure_ascii=False))
