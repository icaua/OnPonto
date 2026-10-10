from datetime import date,time
from pathlib import Path
import json,sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine,event
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.database.session import Base
from app.database.models import Competencia,CacheConferencia,MarcacaoPonto,Escala,Funcionario,ArquivoRecebido,EventoCalendario
from app.apuracao.contexto import ContextoApuracao
from app.apuracao.triagem import consultar_triagem
from app.apuracao.service import apurar_competencia
from app.apuracao.routes import obter_dias,obter_resumo
from app.competencias.service import sincronizar_status_competencia
from app.competencias.routes import fechar_competencia
from app.competencias.schemas import FechamentoCompetenciaRequest
from synthetic_scenarios import criar_cenario,normalizar


class TriagemIncrementalTest(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db=Session(self.engine)
        self.addCleanup(self.engine.dispose);self.addCleanup(self.db.close)
        self.ids=criar_cenario(self.db,10)

    def test_contadores_equivalentes_sem_escrita_em_get(self):
        antes=self.db.query(CacheConferencia).count()
        triagem=consultar_triagem(self.db,self.ids["aberta"])
        completo=apurar_competencia(self.db,self.ids["aberta"])
        self.assertEqual(triagem["operacional"],completo["operacional"])
        self.assertEqual(triagem["fechamento"]["motivos"],completo["fechamento"]["motivos"])
        self.assertNotIn("marcacoes",triagem)
        self.assertFalse(triagem["apuracao_integral"])
        self.assertEqual(self.db.query(CacheConferencia).count(),antes)
        self.assertFalse(self.db.new);self.assertFalse(self.db.dirty)

    def test_recalcula_apenas_funcionario_modificado_e_invalida_contexto(self):
        c=self.db.get(Competencia,self.ids["aberta"])
        sincronizar_status_competencia(self.db,c);self.db.commit()
        self.assertEqual(self.db.query(CacheConferencia).count(),10)
        m=self.db.query(MarcacaoPonto).filter_by(competencia_id=c.id,funcionario_id=2,data=date(2026,9,2)).one()
        m.entrada=time(8,15);self.db.flush()
        original=ContextoApuracao.detalhes
        with patch.object(ContextoApuracao,"detalhes",autospec=True,side_effect=original) as chamadas:
            sincronizar_status_competencia(self.db,c)
            self.assertEqual([x.args[1] for x in chamadas.call_args_list],[2])
        self.db.commit()
        with patch.object(ContextoApuracao,"detalhes",autospec=True,side_effect=original) as chamadas:
            consultar_triagem(self.db,c.id)
            self.assertEqual(chamadas.call_count,0)
        self.db.get(Funcionario,3).data_demissao=date(2026,9,1);self.db.flush()
        with patch.object(ContextoApuracao,"detalhes",autospec=True,side_effect=original) as chamadas:
            consultar_triagem(self.db,c.id)
            self.assertEqual([x.args[1] for x in chamadas.call_args_list],[3])
        self.db.get(Escala,1).tolerancia_atraso_minutos=0;self.db.flush()
        with patch.object(ContextoApuracao,"detalhes",autospec=True,side_effect=original) as chamadas:
            consultar_triagem(self.db,c.id)
            self.assertGreater(chamadas.call_count,0)

    def test_fechamento_recalcula_sem_confiar_em_cache(self):
        c=self.db.get(Competencia,self.ids["aberta"])
        sincronizar_status_competencia(self.db,c);self.db.commit()
        for r in self.db.query(CacheConferencia):
            dados=json.loads(r.contadores_json)
            dados.update(problema=0,aguardando_conferencia=0,conferido=dados["total"])
            r.contadores_json=json.dumps(dados)
        self.db.commit()
        with self.assertRaises(HTTPException) as erro: fechar_competencia(c.id,FechamentoCompetenciaRequest(),self.db)
        self.assertEqual(erro.exception.status_code,409)
        self.assertNotEqual(c.status,"fechada")

    def test_endpoints_reduzidos_iguais_ao_motor_aberto_e_snapshot(self):
        c=self.ids["fechavel"]
        for fechado in (False,True):
            if fechado: fechar_competencia(c,FechamentoCompetenciaRequest(),self.db)
            completo=apurar_competencia(self.db,c)
            resumo=obter_resumo(c,self.db)
            self.assertNotIn("marcacoes",resumo);self.assertNotIn("pendencias",resumo)
            self.assertEqual(normalizar(resumo["resumo"]),normalizar(completo["resumo"]))
            for f in (1,2,3):
                dias=obter_dias(c,f,self.db)["marcacoes"]
                self.assertEqual(normalizar(dias),normalizar([d for d in completo["marcacoes"] if d["funcionario_id"]==f]))

    def test_consultas_em_lote_nao_crescem_por_funcionario_do_banco(self):
        sql=[]
        def contar(conn,cursor,statement,parameters,context,executemany): sql.append(statement)
        event.listen(self.engine,"before_cursor_execute",contar)
        self.addCleanup(event.remove,self.engine,"before_cursor_execute",contar)
        apurar_competencia(self.db,self.ids["aberta"])
        self.assertLessEqual(len(sql),18)
        ledger=[s for s in sql if s.lstrip().startswith("SELECT") and "FROM lancamentos_banco_horas" in s]
        self.assertEqual(len(ledger),1)

    def test_listagem_com_muitos_arquivos_carrega_origem_em_uma_consulta(self):
        from app.marcacoes.routes import listar_marcacoes
        from app.marcacoes.schemas import MarcacaoRead
        c=self.ids["aberta"]
        for m in self.db.query(MarcacaoPonto).filter_by(competencia_id=c,funcionario_id=1):
            a=ArquivoRecebido(competencia_id=c,nome_original=f"FICTÍCIO-{m.id}.txt",caminho_arquivo=f"ficticio-{m.id}.txt",tipo_arquivo="txt")
            self.db.add(a);self.db.flush();m.arquivo_origem_id=a.id
        self.db.commit();self.db.expunge_all()
        sql=[]
        def contar(conn,cursor,statement,parameters,context,executemany): sql.append(statement)
        event.listen(self.engine,"before_cursor_execute",contar)
        self.addCleanup(event.remove,self.engine,"before_cursor_execute",contar)
        marcacoes=listar_marcacoes(c,1,self.db)
        lidas=[MarcacaoRead.model_validate(m) for m in marcacoes]
        self.assertEqual(len(lidas),30)
        self.assertTrue(all(m.arquivo_origem_nome.startswith("FICTÍCIO-") for m in lidas))
        self.assertEqual(len(sql),1)

    def test_cache_dsr_invalida_quando_referencia_de_outro_mes_muda(self):
        s=self.db.get(Escala,1);s.politica_dsr={"versao":1,"dia_descanso":6,"descontar_feriados":True}
        self.db.add(EventoCalendario(nome="FRONTEIRA FICTÍCIA",data=date(2026,9,30),tipo="FERIADO",abrangencia="EMPRESA",empresa_id=self.ids["empresa"]))
        self.db.flush()
        c=self.db.get(Competencia,self.ids["aberta"])
        sincronizar_status_competencia(self.db,c);self.db.commit()
        fonte=self.db.query(MarcacaoPonto).filter_by(funcionario_id=1,data=date(2026,10,1)).one()
        fonte.conferido=False;self.db.flush()
        original=ContextoApuracao.detalhes
        with patch.object(ContextoApuracao,"detalhes",autospec=True,side_effect=original) as chamadas:
            triagem=consultar_triagem(self.db,c.id)
            self.assertEqual([x.args[1] for x in chamadas.call_args_list],[1])
        self.assertEqual(triagem["operacional"],apurar_competencia(self.db,c.id)["operacional"])
