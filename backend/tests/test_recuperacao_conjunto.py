from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
import json
from datetime import date,time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.database.recuperacao import criar_conjunto,restaurar_conjunto,sha256
from app.database.migrations import aplicar_migracoes_compativeis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.database.session import Base
from app.database.models import Empresa,Escala,Funcionario,Competencia,ArquivoRecebido,MarcacaoPonto,DocumentoEvidencia,OcorrenciaFuncionario
from app.evidencias.inventario import verificar


class RecuperacaoConjuntoTest(unittest.TestCase):
    def test_backup_restore_schema_antigo_e_evidencias(self):
        with tempfile.TemporaryDirectory(prefix="onponto-conjunto-") as temp:
            root=Path(temp)
            banco=root/"ficticio.db"
            with closing(sqlite3.connect(banco)) as db:
                db.executescript("CREATE TABLE evidencia (id INTEGER PRIMARY KEY,original TEXT); INSERT INTO evidencia VALUES (1,'FICTÍCIO'); PRAGMA user_version=7;")
                db.commit()
            uploads=root/"uploads"
            uploads.mkdir()
            (uploads/"ficticio.txt").write_text("Batidas FICTÍCIAS 08:00 12:00 13:00 17:00",encoding="utf-8")
            original=sha256(banco)
            manifest=criar_conjunto(banco,uploads,root/"backup",offline=True)
            restaurar_conjunto(root/"backup",root/"restaurado")
            self.assertEqual(manifest["banco_sha256"],sha256(root/"restaurado"/"onponto.db"))
            with closing(sqlite3.connect(banco)) as fonte, closing(sqlite3.connect(root/"restaurado"/"onponto.db")) as copia:
                self.assertEqual(list(fonte.iterdump()),list(copia.iterdump()))
                self.assertEqual(fonte.execute("PRAGMA user_version").fetchone(),copia.execute("PRAGMA user_version").fetchone())
            self.assertEqual(sha256(uploads/"ficticio.txt"),manifest["arquivos"]["ficticio.txt"])
            engine=create_engine(f"sqlite:///{root/'restaurado'/'onponto.db'}")
            try:
                aplicar_migracoes_compativeis(engine)
                aplicar_migracoes_compativeis(engine)
                with engine.connect() as conn:
                    self.assertEqual(conn.exec_driver_sql("SELECT original FROM evidencia").scalar_one(),"FICTÍCIO")
                    self.assertEqual(conn.exec_driver_sql("PRAGMA foreign_key_check").all(),[])
                    self.assertEqual(conn.exec_driver_sql("PRAGMA integrity_check").scalar_one(),"ok")
            finally: engine.dispose()
            self.assertEqual(original,sha256(banco))
            with self.assertRaises(FileExistsError): restaurar_conjunto(root/"backup",root/"restaurado")
            (root/"backup"/"uploads"/"ficticio.txt").write_text("adulteração",encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError,"Hash de arquivo"):
                restaurar_conjunto(root/"backup",root/"recusado")
            self.assertFalse((root/"recusado").exists())

    def test_exige_escritores_parados(self):
        with self.assertRaisesRegex(ValueError,"Pare a API"):
            criar_conjunto("ignorado","ignorado","ignorado")

    def test_restore_portatil_preserva_evidencia_e_migracao_repetida(self):
        with tempfile.TemporaryDirectory(prefix='onponto-portatil-') as temp:
            root=Path(temp);backend=root/'fonte';uploads=backend/'uploads';uploads.mkdir(parents=True)
            arquivo=uploads/'original.txt';arquivo.write_bytes(b'FICTICIO 08:00 12:00 13:00 17:00')
            anexo=uploads/'ocorrencias'/'1'/'atestado.pdf';anexo.parent.mkdir(parents=True);anexo.write_bytes(b'%PDF-FICTICIO')
            banco=backend/'onponto.db';engine=create_engine('sqlite:///'+banco.as_posix())
            Base.metadata.create_all(engine)
            with Session(engine) as db:
                e=Empresa(nome='FICTICIA');db.add(e);db.flush()
                s=Escala(empresa_id=e.id,nome='FICTICIA');db.add(s);db.flush()
                f=Funcionario(empresa_id=e.id,escala_id=s.id,nome='FICTICIO',codigo='F1');db.add(f);db.flush()
                c=Competencia(empresa_id=e.id,mes=9,ano=2026);db.add(c);db.flush()
                a=ArquivoRecebido(competencia_id=c.id,nome_original='original.txt',tipo_arquivo='txt',caminho_arquivo=arquivo.as_posix(),sha256=sha256(arquivo));db.add(a);db.flush()
                db.add(MarcacaoPonto(competencia_id=c.id,funcionario_id=f.id,data=date(2026,9,1),entrada=time(8),batidas_originais='["08:00","08:00"]',arquivo_origem_id=a.id))
                db.add(DocumentoEvidencia(arquivo_id=a.id,referencia_legada=arquivo.as_posix(),nome_original='original.txt',origem='legado',sha256=None))
                db.add(OcorrenciaFuncionario(funcionario_id=f.id,tipo='ATESTADO',data_inicio=date(2026,9,1),data_fim=date(2026,9,1),anexo_caminho='ocorrencias/1/atestado.pdf',anexo_nome='atestado.pdf'))
                db.commit()
                from synthetic_scenarios import criar_cenario
                from app.competencias.routes import fechar_competencia
                from app.competencias.schemas import FechamentoCompetenciaRequest
                ids=criar_cenario(db,3);db.commit()
                fechar_competencia(ids['fechavel'],FechamentoCompetenciaRequest(),db)
            aplicar_migracoes_compativeis(engine);engine.dispose()
            with closing(sqlite3.connect(banco)) as db:
                antigos={t:db.execute('SELECT * FROM '+t).fetchall() for t in ('documentos_evidencia','batidas_originais','eventos_auditoria','escala_versoes','fechamentos_versoes','lancamentos_banco_horas','compensacoes_banco_horas')}
            hash_fonte=sha256(banco)
            criar_conjunto(banco,uploads,root/'copia',offline=True)
            restaurar_conjunto(root/'copia',root/'nova')
            novo=create_engine('sqlite:///'+(root/'nova'/'onponto.db').as_posix())
            try:
                aplicar_migracoes_compativeis(novo);aplicar_migracoes_compativeis(novo)
                with Session(novo) as db:
                    invent=verificar(db,root/'nova'/'uploads',root/'nova')
                    self.assertEqual(invent['ausentes'],[]);self.assertEqual(invent['hash_divergente'],[]);self.assertEqual(invent['referencias_invalidas'],[])
                    self.assertTrue(Path(db.get(ArquivoRecebido,1).caminho_arquivo).is_relative_to(root/'nova'))
                with closing(sqlite3.connect(root/'nova'/'onponto.db')) as db:
                    for t,linhas in antigos.items():self.assertEqual(db.execute('SELECT * FROM '+t).fetchall(),linhas)
                    self.assertEqual(db.execute('PRAGMA integrity_check').fetchone(),('ok',));self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
            finally:novo.dispose()
            self.assertEqual(sha256(banco),hash_fonte)
            manifesto=root/'copia'/'manifest.json';dados=json.loads(manifesto.read_text());dados['referencias'][arquivo.as_posix()]='../fora.txt';manifesto.write_text(json.dumps(dados))
            with self.assertRaisesRegex(RuntimeError,'Mapeamento'):restaurar_conjunto(root/'copia',root/'recusada')
            self.assertFalse((root/'recusada').exists())

    def test_wal_backup_consistente_e_exclusao_de_escritores(self):
        with tempfile.TemporaryDirectory(prefix='onponto-wal-') as temp:
            root=Path(temp);banco=root/'ficticio.db';uploads=root/'uploads';uploads.mkdir()
            with closing(sqlite3.connect(banco,timeout=.05)) as escritor,closing(sqlite3.connect(banco,timeout=.05)) as concorrente:
                self.assertEqual(escritor.execute('PRAGMA journal_mode=WAL').fetchone(),('wal',))
                escritor.execute('CREATE TABLE teste(id INTEGER PRIMARY KEY,valor TEXT)');escritor.execute("INSERT INTO teste VALUES(1,'FICTICIO')");escritor.commit()
                escritor.execute('BEGIN IMMEDIATE');escritor.execute("UPDATE teste SET valor='NAO COMMITADO'")
                with self.assertRaises(sqlite3.OperationalError):concorrente.execute('BEGIN IMMEDIATE')
                self.assertEqual(concorrente.execute('SELECT valor FROM teste').fetchone(),('FICTICIO',));escritor.rollback()
                criar_conjunto(banco,uploads,root/'backup',offline=True);restaurar_conjunto(root/'backup',root/'restore')
                with closing(sqlite3.connect(root/'restore'/'onponto.db')) as copia:self.assertEqual(copia.execute('SELECT valor FROM teste').fetchone(),('FICTICIO',))
