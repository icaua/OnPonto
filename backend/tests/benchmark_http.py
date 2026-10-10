"""Benchmark HTTP sequencial: nunca conecta ao DB ou uploads da instalação.

Execução: .venv/Scripts/python.exe backend/tests/benchmark_http.py --output docs/benchmarks/00-baseline.json
Instrumentação existe apenas neste processo de teste; não há rota de diagnóstico em produção.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import tracemalloc
from urllib.request import Request,urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))


def serve(port,quantidade):
    if not os.environ.get("ONPONTO_BENCHMARK_ISOLATED"):
        raise RuntimeError("Benchmark exige ambiente isolado explícito.")
    from sqlalchemy import event
    from app.database.session import Base,engine,SessionLocal
    from app.database.migrations import aplicar_migracoes_compativeis
    from synthetic_scenarios import criar_cenario
    Base.metadata.create_all(engine)
    aplicar_migracoes_compativeis(engine)
    with SessionLocal() as db: criar_cenario(db,quantidade)
    from app.main import app
    import uvicorn
    consultas=[0]
    @event.listens_for(engine,"before_cursor_execute")
    def contar(*args): consultas[0]+=1
    tracemalloc.start()
    @app.middleware("http")
    async def medir(request,call_next):
        consultas[0]=0
        tracemalloc.reset_peak()
        inicial=tracemalloc.get_traced_memory()[0]
        response=await call_next(request)
        response.headers["X-Benchmark-Sql"]=str(consultas[0])
        response.headers["X-Benchmark-Peak"]=str(max(0,tracemalloc.get_traced_memory()[1]-inicial))
        return response
    uvicorn.run(app,host="127.0.0.1",port=port,log_level="error")


def requisicao(base,nome,path,method="GET",body=None):
    start=time.perf_counter()
    req=Request(base+path,data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type":"application/json"},method=method)
    with urlopen(req,timeout=300) as response:
        data=response.read()
        return {"operacao":nome,"metodo":method,"path":path,"status":response.status,
            "sql_queries":int(response.headers["X-Benchmark-Sql"]),
            "latencia_ms":round((time.perf_counter()-start)*1000,3),
            "pico_python_incremental_bytes":int(response.headers["X-Benchmark-Peak"]),
            "response_bytes":len(data)}


def medir(quantidade):
    with tempfile.TemporaryDirectory(prefix="onponto-benchmark-") as temp:
        root=Path(temp)
        with socket.socket() as s:
            s.bind(("127.0.0.1",0));port=s.getsockname()[1]
        env={**os.environ,"ONPONTO_BENCHMARK_ISOLATED":"1",
            "ONPONTO_DATABASE_URL":f"sqlite:///{root/'ficticio.test.db'}",
            "ONPONTO_UPLOADS_DIR":str(root/"uploads"),"ONPONTO_BACKUP_DIR":str(root/"backups")}
        with (root/"servidor.log").open("w",encoding="utf-8") as log:
            process=subprocess.Popen([sys.executable,__file__,"--serve",str(port),"--count",str(quantidade)],
                env=env,stdout=log,stderr=subprocess.STDOUT)
            base=f"http://127.0.0.1:{port}"
            try:
                for _ in range(1200):
                    if process.poll() is not None:
                        raise RuntimeError((root/"servidor.log").read_text(encoding="utf-8"))
                    try:
                        with urlopen(base,timeout=1): break
                    except OSError: time.sleep(.1)
                else: raise RuntimeError("API fictícia não iniciou.")
                rows=[]
                for rep in range(3):
                    rows.append(dict(requisicao(base,"GET /apuracao","/apuracao?competencia_id=1"),repeticao=rep+1))
                with urlopen(base+"/marcacoes/31",timeout=300) as response:
                    revisao=json.load(response)["revisao"]
                rows.append(requisicao(base,"PATCH marcação","/marcacoes/31","PATCH",{"entrada":"08:01","revisao":revisao}))
                with urlopen(base+"/marcacoes?competencia_id=2",timeout=300) as response:
                    revisoes={m["id"]:m["revisao"] for m in json.load(response)}
                rows.append(requisicao(base,"confirmar lote","/marcacoes/conferir-lote","POST",
                    {"competencia_id":2,"marcacoes_ids":[31+i*61 for i in range(min(quantidade,1000))],"revisoes":revisoes}))
                rows.append(requisicao(base,"abrir conferência","/marcacoes?competencia_id=1"))
                rows.append(requisicao(base,"fechar","/competencias/2/fechar","POST",{}))
                rows.append(requisicao(base,"exportar Excel","/relatorios/excel?competencia_id=2"))
                rows.append(requisicao(base,"extrato","/banco-horas/extrato?funcionario_id=2"))
                rows.append(requisicao(base,"saldo","/banco-horas/saldo?funcionario_id=2"))
                rows.append(requisicao(base,"reabrir","/competencias/2/reabrir","POST",{}))
                return {"funcionarios":quantidade,"dias":[30,31],"marcacoes":quantidade*61,
                    "db_bytes":(root/"ficticio.test.db").stat().st_size,"medicoes":rows}
            finally:
                process.terminate()
                process.wait(timeout=10)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--serve",type=int)
    parser.add_argument("--count",type=int,default=10)
    parser.add_argument("--counts",type=int,nargs="+",default=[50,250,1000])
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    if args.serve: serve(args.serve,args.count)
    else:
        import sqlalchemy,fastapi
        result={"python":platform.python_version(),"sqlite":sqlite3.sqlite_version,
            "sqlalchemy":sqlalchemy.__version__,"fastapi":fastapi.__version__,
            "plataforma":platform.platform(),"cenario":"synthetic_scenarios.criar_cenario v1",
            "metodo":"HTTP real em loopback; SQL via evento engine; pico incremental tracemalloc do handler; latência inclui transferência. GET repetido 3 vezes; mutações 1 vez. Tracing ativo em todas as fases.",
            "cenarios":[]}
        for count in args.counts:
            print(f"Medindo {count} funcionários...",flush=True)
            result["cenarios"].append(medir(count))
            if args.output:
                args.output.parent.mkdir(parents=True,exist_ok=True)
                args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({"output":str(args.output),"cenarios":len(result["cenarios"])},ensure_ascii=False))
