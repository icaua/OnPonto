from dataclasses import replace
from datetime import date, time, timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.database.session import Base
from app.database.models import Empresa, Escala, Funcionario, Competencia, MarcacaoPonto, EventoCalendario, FechamentoVersao, DependenciaFechamento
from app.database.migrations import aplicar_migracoes_compativeis
from app.dominio.dsr import DiaReferenciaDSR, apurar_descanso
from app.apuracao.service import apurar_competencia
from app.competencias.routes import fechar_competencia, reabrir_competencia
from app.competencias.schemas import FechamentoCompetenciaRequest
from app.marcacoes.routes import atualizar_marcacao
from app.marcacoes.schemas import MarcacaoUpdate
from app.ocorrencias.service import validar_fechadas
from app.ocorrencias.schemas import OcorrenciaCreate


class DSRPuroTest(unittest.TestCase):
    def test_uma_ou_varias_faltas_perdem_so_um_dsr_e_justificadas_nao(self):
        descanso=date(2026,9,6)
        refs=[DiaReferenciaDSR(descanso-timedelta(days=6-i),True,i+1,1,"normal",True) for i in range(6)]
        for status,esperado in (("falta",1),("falta_justificada",0),("atestado",0),("normal",0),("folga",0)):
            with self.subTest(status=status):
                dados=[replace(d,status=status) if i<2 else d for i,d in enumerate(refs)]
                self.assertEqual(apurar_descanso(descanso,dados)["desconto_dias"],esperado)

    def test_referencia_incompleta_nao_fabrica_resultado_zero(self):
        resultado=apurar_descanso(date(2026,9,6),[])
        self.assertIsNone(resultado["desconto_dias"])
        self.assertEqual(len(resultado["dias_pendentes"]),6)


class DSRIntegracaoTest(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.db=Session(self.engine)
        self.addCleanup(self.db.close)
        e=Empresa(nome="FICTÍCIA DSR");self.db.add(e);self.db.flush()
        s=Escala(empresa_id=e.id,nome="FICTÍCIA DSR",jornada_seg_sex_horas=8,
                 politica_dsr={"versao":1,"dia_descanso":6,"descontar_feriados":True,"referencia":"Política do usuário"})
        self.db.add(s);self.db.flush()
        f=Funcionario(empresa_id=e.id,nome="FICTÍCIO",escala_id=s.id,data_admissao=date(2026,9,1))
        self.db.add(f);self.db.flush()
        c=Competencia(empresa_id=e.id,mes=9,ano=2026)
        futuro=Competencia(empresa_id=e.id,mes=10,ano=2026)
        self.db.add_all([c,futuro]);self.db.flush()
        for n in range(1,31):
            self.db.add(MarcacaoPonto(competencia_id=c.id,funcionario_id=f.id,data=date(2026,9,n),
                status_dia="sem_expediente",conferido=True))
        self.db.add(EventoCalendario(nome="FERIADO FICTÍCIO",data=date(2026,9,4),tipo="FERIADO",abrangencia="EMPRESA",empresa_id=e.id))
        self.db.commit()
        aplicar_migracoes_compativeis(self.engine)
        self.e,self.s,self.f,self.c,self.futuro=e,s,f,c,futuro

    def marcacao(self, data):
        return self.db.query(MarcacaoPonto).filter_by(funcionario_id=self.f.id,data=data).one()

    def test_desconta_descanso_e_feriado_da_semana_sem_dupla_falta(self):
        for dia in (1,2): self.marcacao(date(2026,9,dia)).status_dia="falta"
        self.db.commit()
        r=apurar_competencia(self.db,self.c.id)
        self.assertEqual(r["resumo"][0]["dsr_desconto_dias"],2)
        por_data={d["data"]:d for d in r["marcacoes"]}
        self.assertEqual(por_data["2026-09-04"]["dsr"]["desconto_dias"],1)
        self.assertEqual(por_data["2026-09-06"]["dsr"]["desconto_dias"],1)
        self.assertEqual(por_data["2026-09-13"]["dsr"]["desconto_dias"],0)
        self.assertEqual(r["resumo"][0]["atrasos_minutos"],0)

    def test_justificada_atestado_abono_e_atraso_nao_causam_perda(self):
        for status in ("falta_justificada","atestado","normal"):
            with self.subTest(status=status):
                m=self.marcacao(date(2026,9,1));m.status_dia=status
                m.observacoes="Motivo FICTÍCIO documentado para teste"
                m.entrada=time(10) if status=="normal" else None
                m.saida=time(17) if status=="normal" else None
                self.db.commit()
                self.assertEqual(apurar_competencia(self.db,self.c.id)["resumo"][0]["dsr_desconto_dias"],0)

    def test_descanso_em_outro_dia_conforme_escala(self):
        # Fixture de cadastro novo sem edição de versão existente.
        from app.escalas.routes import atualizar
        from app.escalas.schemas import EscalaUpdate
        atualizar(self.s.id,EscalaUpdate(politica_dsr={"dia_descanso":0},vigente_desde=date(2026,9,1)),self.db)
        # A alteração de regra exige revisão humana dos dias abertos.
        for m in self.db.query(MarcacaoPonto): m.conferido=True
        self.marcacao(date(2026,9,1)).status_dia="falta"
        self.db.commit()
        r=apurar_competencia(self.db,self.c.id)
        por_data={d["data"]:d for d in r["marcacoes"]}
        self.assertEqual(por_data["2026-09-07"]["dsr"]["periodo_inicio"],"2026-09-01")
        self.assertEqual(por_data["2026-09-07"]["dsr"]["desconto_dias"],1)
        self.assertNotIn("dsr",por_data["2026-09-06"])

    def test_feriado_coincidente_com_descanso_conta_uma_data(self):
        self.db.add(EventoCalendario(nome="DOMINGO FICTÍCIO",data=date(2026,9,6),tipo="FERIADO",abrangencia="EMPRESA",empresa_id=self.e.id))
        self.marcacao(date(2026,9,1)).status_dia="falta"
        self.db.commit()
        r=apurar_competencia(self.db,self.c.id)
        self.assertEqual(r["resumo"][0]["dsr_dias"],5)
        self.assertEqual(r["resumo"][0]["dsr_desconto_dias"],2)

    def test_feriado_cruza_competencia_pendente_e_fechamento_protege_referencia(self):
        self.db.add(EventoCalendario(nome="FRONTEIRA FICTÍCIA",data=date(2026,9,30),tipo="FERIADO",abrangencia="EMPRESA",empresa_id=self.e.id))
        self.db.commit()
        r=apurar_competencia(self.db,self.c.id)
        self.assertIsNone(r["resumo"][0]["dsr_desconto_dias"])
        self.assertFalse(r["fechamento"]["pode_fechar"])
        for n in range(1,4):
            self.db.add(MarcacaoPonto(competencia_id=self.futuro.id,funcionario_id=self.f.id,data=date(2026,10,n),
                status_dia="falta" if n==1 else "sem_expediente",conferido=True))
        self.db.commit()
        fechar_competencia(self.c.id,FechamentoCompetenciaRequest(),self.db)
        original=self.db.query(FechamentoVersao).one().snapshot
        fonte=self.marcacao(date(2026,10,1))
        self.assertTrue(self.db.query(DependenciaFechamento).filter_by(marcacao_id=fonte.id).first())
        from app.calendario.routes import criar_evento
        from app.calendario.schemas import EventoCreate
        from app.escalas.routes import atualizar
        from app.escalas.schemas import EscalaUpdate
        from app.funcionarios.routes import atualizar_funcionario
        from app.funcionarios.schemas import FuncionarioUpdate
        for operacao in (
            lambda:criar_evento(EventoCreate(nome="NOVO FICTÍCIO",data=date(2026,10,1),tipo="FERIADO",abrangencia="EMPRESA",empresa_id=self.e.id),self.db),
            lambda:atualizar(self.s.id,EscalaUpdate(jornada_seg_sex_horas=7,vigente_desde=date(2026,10,1)),self.db),
            lambda:atualizar_funcionario(self.f.id,FuncionarioUpdate(data_demissao=date(2026,9,30)),self.db)):
            with self.assertRaises(HTTPException) as erro: operacao()
            self.assertEqual(erro.exception.status_code,409)
            self.db.rollback()
        with self.assertRaises(HTTPException) as erro:
            atualizar_marcacao(fonte.id,MarcacaoUpdate(status_dia="falta_justificada",observacoes="Motivo FICTÍCIO suficiente",revisao=fonte.revisao),self.db)
        self.assertEqual(erro.exception.status_code,409)
        with self.assertRaises(HTTPException):
            validar_fechadas(self.db,OcorrenciaCreate(funcionario_id=self.f.id,tipo="ATESTADO",data_inicio=date(2026,10,1),data_fim=date(2026,10,1)))
        reabrir_competencia(self.c.id,self.db)
        atualizar_marcacao(fonte.id,MarcacaoUpdate(status_dia="falta_justificada",observacoes="Motivo FICTÍCIO suficiente",revisao=fonte.revisao),self.db)
        fechar_competencia(self.c.id,FechamentoCompetenciaRequest(),self.db)
        self.assertEqual(self.db.query(FechamentoVersao).filter_by(numero=1).one().snapshot,original)
        self.assertEqual(apurar_competencia(self.db,self.c.id)["resumo"][0]["dsr_desconto_dias"],0)
