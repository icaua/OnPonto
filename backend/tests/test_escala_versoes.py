from dataclasses import replace
from datetime import date,time
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database.session import Base
from app.database.models import Empresa,Escala,EscalaVersao,Funcionario,Competencia,MarcacaoPonto
from app.database.migrations import aplicar_migracoes_compativeis
from app.escalas.routes import atualizar
from app.escalas.schemas import EscalaUpdate
from app.apuracao.service import apurar_competencia
from app.funcionarios.historico_escalas import ResolvedorEscalas


class EscalaVersoesTest(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.db=Session(self.engine)
        self.addCleanup(self.db.close)
        e=Empresa(nome="FICTÍCIA temporal");self.db.add(e);self.db.flush()
        self.escala=Escala(empresa_id=e.id,nome="FICTÍCIA",modo_apuracao="horario_fixo",
            horario_entrada_prevista=time(8),horario_saida_almoco_prevista=time(12),
            horario_retorno_almoco_prevista=time(13),horario_saida_prevista=time(17),regime_sabado="trabalha")
        self.db.add(self.escala);self.db.flush()
        f=Funcionario(empresa_id=e.id,nome="FICTÍCIO",escala_id=self.escala.id)
        self.db.add(f);self.db.flush()
        self.funcionario=f
        for mes in (9,10):
            c=Competencia(empresa_id=e.id,ano=2026,mes=mes);self.db.add(c);self.db.flush()
            self.db.add(MarcacaoPonto(competencia_id=c.id,funcionario_id=f.id,data=date(2026,mes,1),
                entrada=time(8),saida_almoco=time(12),retorno_almoco=time(13),saida=time(17),conferido=True))
        self.db.commit()
        aplicar_migracoes_compativeis(self.engine)

    def test_outubro_nao_muda_setembro_e_invalida_conferencia(self):
        antes=apurar_competencia(self.db,1)["marcacoes"][0]
        atualizar(self.escala.id,EscalaUpdate(horario_saida_prevista=time(18),vigente_desde=date(2026,10,1)),self.db)
        setembro=apurar_competencia(self.db,1)["marcacoes"][0]
        outubro=apurar_competencia(self.db,2)["marcacoes"][0]
        self.assertEqual(setembro,antes)
        self.assertEqual(outubro["jornada_prevista_minutos"],540)
        self.assertFalse(outubro["conferido"])
        resolvido=ResolvedorEscalas(self.db,self.escala.empresa_id)
        self.assertEqual(resolvido.regra_no_dia(self.funcionario,date(2026,9,30)).horario_saida_prevista,time(17))
        self.assertEqual(resolvido.regra_no_dia(self.funcionario,date(2026,10,1)).horario_saida_prevista,time(18))

    def test_sabado_quatro_horas_e_precedencia_domingo_feriado(self):
        jornadas={"5":{"jornada_minutos":240,"horario_entrada_prevista":"08:00","horario_saida_prevista":"12:00"}}
        atualizar(self.escala.id,EscalaUpdate(jornadas_semana=jornadas,vigente_desde=date(2026,9,1)),self.db)
        from app.dominio.apuracao import apurar_dia
        from app.dominio.contratos import FuncionarioDoDia,MarcacoesDoDia,ContextoCalendario
        r=ResolvedorEscalas(self.db,self.escala.empresa_id).regra_no_dia(self.funcionario,date(2026,9,5))
        f=FuncionarioDoDia(1,"FICTÍCIO",r)
        m=MarcacoesDoDia(1,date(2026,9,5),entrada=time(8),saida=time(12),conferido=True)
        resultado=apurar_dia(f,m)
        self.assertEqual((resultado.previstos_minutos,resultado.trabalhados_minutos,resultado.extra_minutos),(240,240,0))
        self.assertEqual(apurar_dia(f,m,ContextoCalendario(("FICTÍCIO",))).previstos_minutos,0)
        domingo=replace(m,data=date(2026,9,6),status_dia="domingo",entrada=None,saida=None)
        self.assertEqual(apurar_dia(f,domingo).previstos_minutos,0)

    def test_snapshot_fechado_identico_e_vigencia_conflitante_recusada(self):
        c=self.db.get(Competencia,1)
        c.status="fechada";c.apuracao_fechada='{"FICTÍCIO":"snapshot bytes preservados"}'
        self.db.commit()
        snapshot=c.apuracao_fechada
        atualizar(self.escala.id,EscalaUpdate(horario_saida_prevista=time(18),vigente_desde=date(2026,10,1)),self.db)
        self.assertEqual(self.db.get(Competencia,1).apuracao_fechada,snapshot)
        with self.assertRaises(HTTPException) as erro:
            atualizar(self.escala.id,EscalaUpdate(horario_saida_prevista=time(19),vigente_desde=date(2026,9,1)),self.db)
        self.assertEqual(erro.exception.status_code,409)
        self.assertEqual(self.db.query(EscalaVersao).count(),2)

    def test_migracao_idempotente_json_imutavel_sobreposicao_recusada(self):
        antes=self.db.query(EscalaVersao).one()
        original=antes.configuracao_json
        self.assertIsNone(antes.vigente_desde)
        self.assertEqual(antes.origem,"legado_vigencia_desconhecida")
        self.db.rollback()
        aplicar_migracoes_compativeis(self.engine)
        self.assertEqual(self.db.query(EscalaVersao).count(),1)
        with self.assertRaises(IntegrityError):
            self.db.execute(__import__('sqlalchemy').text("UPDATE escala_versoes SET configuracao_json='{}'"))
        self.db.rollback()
        self.db.add(EscalaVersao(escala_id=self.escala.id,numero=2,vigente_desde=date(2026,10,1),
            configuracao_json=original,origem="FICTÍCIA"))
        with self.assertRaises(IntegrityError): self.db.flush()
        self.db.rollback()
        with self.engine.connect() as c:
            self.assertEqual(c.exec_driver_sql("PRAGMA foreign_key_check").all(),[])
            self.assertEqual(c.exec_driver_sql("PRAGMA integrity_check").scalar_one(),"ok")

    def test_omissao_vigencia_usa_futuro_e_zero_intervalo_preservado(self):
        with patch("app.escalas.versoes.hoje_local",return_value=date(2026,10,10)):
            atualizar(self.escala.id,EscalaUpdate(tolerancia_intervalo_minutos=0),self.db)
        versao=self.db.query(EscalaVersao).order_by(EscalaVersao.numero.desc()).first()
        self.assertEqual(versao.vigente_desde,date(2026,10,11))
        self.assertEqual(json.loads(versao.configuracao_json)["tolerancia_intervalo_minutos"],0)

    def test_edicoes_sucessivas_sem_data_nao_reescrevem_versao_agendada(self):
        with patch("app.escalas.versoes.hoje_local",return_value=date(2026,10,10)):
            atualizar(self.escala.id,EscalaUpdate(tolerancia_atraso_minutos=5),self.db)
            primeira=self.db.query(EscalaVersao).filter_by(numero=2).one().configuracao_json
            atualizar(self.escala.id,EscalaUpdate(tolerancia_atraso_minutos=10),self.db)
        versoes=self.db.query(EscalaVersao).order_by(EscalaVersao.numero).all()
        self.assertEqual(versoes[1].configuracao_json,primeira)
        self.assertEqual(versoes[1].vigente_desde,date(2026,10,11))
        self.assertEqual(versoes[2].vigente_desde,date(2026,10,12))
        resolvedor=ResolvedorEscalas(self.db,self.escala.empresa_id)
        self.assertEqual(resolvedor.regra_no_dia(self.funcionario,date(2026,10,10)).tolerancia_atraso_minutos,0)
        self.assertEqual(resolvedor.regra_no_dia(self.funcionario,date(2026,10,11)).tolerancia_atraso_minutos,5)
        self.assertEqual(resolvedor.regra_no_dia(self.funcionario,date(2026,10,12)).tolerancia_atraso_minutos,10)
