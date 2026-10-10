from dataclasses import replace
from datetime import date,time
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.dominio.apuracao import apurar_dia
from app.dominio.contratos import (RegraVigente,FuncionarioDoDia,MarcacoesDoDia,
    ContextoCalendario,Ocorrencia,OcorrenciasDoDia)


class MotorPuroTest(unittest.TestCase):
    def setUp(self):
        self.regra=RegraVigente(id=1,modo_apuracao="horario_fixo",
            horario_entrada_prevista=time(9),horario_saida_almoco_prevista=time(12),
            horario_retorno_almoco_prevista=time(13),horario_saida_prevista=time(18),
            tolerancia_atraso_minutos=5,tolerancia_extra_minutos=10)
        self.funcionario=FuncionarioDoDia(1,"FICTÍCIO",self.regra)
        self.dia=MarcacoesDoDia(id=1,data=date(2026,9,1),entrada=time(9),saida_almoco=time(12),
            retorno_almoco=time(13),saida=time(18),conferido=True)

    def test_importa_sem_banco_fastapi_ou_dependencias_da_instalacao(self):
        code="import sys; sys.path.insert(0,'backend'); from app.dominio.apuracao import apurar_dia; assert not any(m=='fastapi' or m=='sqlalchemy' or m.startswith('app.database') for m in sys.modules)"
        result=subprocess.run([sys.executable,"-S","-c",code],cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_tabela_legada_sem_io(self):
        casos=[({},480,0,0),({"entrada":time(9,5)},475,0,0),
            ({"entrada":time(9,6)},474,6,0),({"saida":time(18,10)},490,0,0),
            ({"saida":time(18,11)},491,0,11),({"retorno_almoco":time(13,30)},450,30,0)]
        for campos,trabalho,atraso,extra in casos:
            with self.subTest(campos=campos):
                resultado=apurar_dia(self.funcionario,replace(self.dia,**campos))
                self.assertEqual((resultado.trabalhados_minutos,resultado.atraso_minutos,resultado.extra_minutos),
                    (trabalho,atraso,extra))
                self.assertEqual(resultado.disponibilidade,"completo")

    def test_incompleto_tem_null_no_contrato_e_preserva_adapter_legado(self):
        for campos in ({"saida":None},{"retorno_almoco":None},{"entrada":time(22),"saida":time(6)}):
            with self.subTest(campos=campos):
                resultado=apurar_dia(self.funcionario,replace(self.dia,**campos))
                self.assertEqual(resultado.disponibilidade,"incompleto")
                self.assertIsNone(resultado.trabalhados_minutos)
                self.assertIsNone(resultado.extra_minutos)
                self.assertTrue(resultado.para_api_legada()["pendente_calculo"])

    def test_falta_e_atestado_nao_criam_atraso_ou_he(self):
        for status in ("falta","atestado"):
            dia=replace(self.dia,status_dia=status,entrada=None,saida_almoco=None,retorno_almoco=None,saida=None)
            r=apurar_dia(self.funcionario,dia)
            self.assertEqual((r.atraso_minutos,r.extra_minutos),(0,0))
            self.assertEqual(r.para_api_legada()["falta"],int(status=="falta"))

    def test_ocorrencia_integral_sem_batidas_e_parcial_sem_referencia(self):
        o=OcorrenciasDoDia((Ocorrencia(1,"ATESTADO",self.dia.data,self.dia.data),))
        dia=replace(self.dia,entrada=None,saida_almoco=None,retorno_almoco=None,saida=None)
        r=apurar_dia(self.funcionario,dia,ocorrencias=o)
        self.assertEqual(r.para_api_legada()["minutos_abonados"],480)
        self.assertEqual(r.extra_minutos,0)
        carga=replace(self.funcionario,escala=RegraVigente(1,"carga_horaria",jornada_seg_sex_horas=8))
        parcial=OcorrenciasDoDia((Ocorrencia(2,"DECLARACAO",dia.data,dia.data,time(9),time(10)),))
        self.assertEqual(apurar_dia(carga,self.dia,ocorrencias=parcial).disponibilidade,"incompleto")

    def test_evidencia_nao_e_mutada_e_feriado_usa_contexto(self):
        dia=replace(self.dia,batidas_originais='["09:00","12:00","13:00","18:00"]')
        antes=repr(dia)
        r=apurar_dia(self.funcionario,dia,ContextoCalendario(("FICTÍCIO",)))
        self.assertEqual(r.para_api_legada()["horas_feriado_minutos"],480)
        self.assertEqual(repr(dia),antes)
        payload=r.para_api_legada();payload["horas_feriado_minutos"]=123
        self.assertEqual(r.para_api_legada()["horas_feriado_minutos"],480)

    def test_indisponivel_sem_escala(self):
        r=apurar_dia(replace(self.funcionario,escala=None),self.dia)
        self.assertEqual(r.disponibilidade,"indisponivel")
        self.assertIsNone(r.previstos_minutos)
