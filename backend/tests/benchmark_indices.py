"""EXPLAIN e custo antes/depois, somente SQLite sintético, sem alterar instalação."""
import json,sys,sqlite3,tempfile,time,statistics,platform
from contextlib import closing
from pathlib import Path
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine,text
from sqlalchemy.orm import Session
from app.database.session import Base
from app.database.migrations import aplicar_migracoes_compativeis
from app.competencias.routes import fechar_competencia
from app.competencias.schemas import FechamentoCompetenciaRequest
from app.database.models import HistoricoVinculoEscala,ArquivoRecebido
from synthetic_scenarios import criar_cenario

CANDIDATOS={
 'ix_marcacao_comp_arquivo':'CREATE INDEX ix_marcacao_comp_arquivo ON marcacoes_ponto(competencia_id,arquivo_origem_id)',
 'ix_vinculo_func_inicio_fim':'CREATE INDEX ix_vinculo_func_inicio_fim ON historico_vinculo_escala(funcionario_id,vigente_desde DESC,id DESC,vigente_ate)',
}
CONSULTAS={
 'mes':('SELECT * FROM marcacoes_ponto WHERE competencia_id=? ORDER BY data,funcionario_id',(1,)),
 'pessoa':('SELECT * FROM marcacoes_ponto WHERE competencia_id=? AND funcionario_id=? ORDER BY data,funcionario_id',(1,500)),
 'arquivos':('SELECT DISTINCT arquivo_origem_id FROM marcacoes_ponto WHERE competencia_id=? AND arquivo_origem_id IS NOT NULL',(1,)),
 'vinculo':("SELECT * FROM historico_vinculo_escala WHERE funcionario_id=? AND vigente_desde<=? AND (vigente_ate IS NULL OR vigente_ate>=?) ORDER BY vigente_desde DESC,id DESC LIMIT 1",(500,'2026-09-15','2026-09-15')),
 'ledger':('SELECT * FROM lancamentos_banco_horas WHERE funcionario_id=? AND data_referencia<=? ORDER BY data_referencia,data_lancamento,id',(500,'2026-12-31')),
}
def fase(banco):
 with closing(sqlite3.connect(banco)) as db:
  resultado={}
  for nome,(sql,args) in CONSULTAS.items():
   planos=[r[3] for r in db.execute('EXPLAIN QUERY PLAN '+sql,args)]
   tempos=[]
   for _ in range(7):
    inicio=time.perf_counter();linhas=db.execute(sql,args).fetchall();tempos.append((time.perf_counter()-inicio)*1000)
   resultado[nome]={'planos':planos,'mediana_ms':round(statistics.median(tempos),4),'linhas':len(linhas)}
  return resultado
def main():
 with tempfile.TemporaryDirectory(prefix='onponto-indices-ficticio-') as temp:
  banco=Path(temp)/'ficticio.db';engine=create_engine('sqlite:///'+banco.as_posix());Base.metadata.create_all(engine)
  aplicar_migracoes_compativeis(engine)
  with Session(engine) as db:
   ids=criar_cenario(db,1000);db.commit()
   for i in range(25):db.add(ArquivoRecebido(competencia_id=ids['aberta'],nome_original=f'ficticio-{i}.txt',caminho_arquivo=f'uploads/ficticio-{i}.txt',tipo_arquivo='txt'))
   db.commit()
   db.execute(text('UPDATE marcacoes_ponto SET arquivo_origem_id=(id%25)+1 WHERE competencia_id=:c'),{'c':ids['aberta']});db.commit()
   for f in range(1,1001):
    for ano in range(2016,2026):
     db.add(HistoricoVinculoEscala(funcionario_id=f,escala_id=1,vigente_desde=date(ano,1,1),vigente_ate=date(ano,12,31)))
   db.commit()
   fechar_competencia(ids['fechavel'],FechamentoCompetenciaRequest(),db)
  engine.dispose()
  with closing(sqlite3.connect(banco)) as db:
   for nome in CANDIDATOS: db.execute('DROP INDEX IF EXISTS '+nome)
   db.commit();db.execute('VACUUM')
  antes=fase(banco);tamanho_antes=banco.stat().st_size
  with closing(sqlite3.connect(banco)) as db:
   inicio=time.perf_counter()
   for sql in CANDIDATOS.values():db.execute(sql)
   db.commit();criacao=(time.perf_counter()-inicio)*1000
   db.execute('PRAGMA optimize')
  depois=fase(banco)
  resultado={'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'funcionarios':1000,'marcacoes':61000,'metodo':'7 SELECTs por consulta; mediana local sem tracing; dois índices adicionais, sem remover índices legados','antes':antes,'depois':depois,'db_bytes_antes':tamanho_antes,'db_bytes_depois':banco.stat().st_size,'criacao_indices_ms':round(criacao,3)}
  Path('docs/benchmarks/08-indices.json').write_text(json.dumps(resultado,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  print(json.dumps(resultado,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
