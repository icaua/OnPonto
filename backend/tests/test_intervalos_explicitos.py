from dataclasses import replace
from datetime import date, time
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.dominio.apuracao import apurar_dia
from app.dominio.contratos import RegraVigente, FuncionarioDoDia, MarcacoesDoDia, ContextoCalendario, Ocorrencia, OcorrenciasDoDia
from app.banco_horas.regras import extra_bruta, distribuir_dia
from app.escalas.schemas import EscalaCreate
from types import SimpleNamespace


class IntervalosExplicitosTest(unittest.TestCase):
    def regra(self, **alteracoes):
        return replace(RegraVigente(1,"horario_fixo",horario_entrada_prevista=time(9),
            horario_saida_almoco_prevista=time(12),horario_retorno_almoco_prevista=time(13),
            horario_saida_prevista=time(18),tipo_intervalo="fixo",registro_intervalo="batidas",duracao_intervalo_minutos=60), **alteracoes)

    def apurar(self, horarios, regra=None, ocorrencias=(), calendario=()):
        r=regra or self.regra()
        m=MarcacoesDoDia(1,date(2026,9,1),**dict(zip(("entrada","saida_almoco","retorno_almoco","saida"),
            (time.fromisoformat(h) if h else None for h in horarios))),conferido=True)
        return apurar_dia(FuncionarioDoDia(1,"FICTÍCIO",r),m,ContextoCalendario(calendario),OcorrenciasDoDia(ocorrencias)),m,r

    def test_matriz_fixo_flexivel_preassinalado_e_pendencias(self):
        casos=[("fixo","batidas",("09:00","12:00","13:00","18:00"),480,0,0),
               ("flexivel","batidas",("09:00","12:35","13:35","18:00"),480,0,0),
               ("flexivel","batidas",("09:00","12:00","13:30","18:00"),450,30,0),
               ("fixo","pre_assinalado",("09:00",None,None,"18:00"),480,0,0),
               ("fixo","pre_assinalado",("09:00","12:00","13:00","18:00"),480,0,0)]
        for tipo,registro,horarios,trabalho,atraso,extra in casos:
            with self.subTest(tipo=tipo,registro=registro,horarios=horarios):
                resultado,m,r=self.apurar(horarios,self.regra(tipo_intervalo=tipo,registro_intervalo=registro))
                self.assertEqual((resultado.trabalhados_minutos,resultado.atraso_minutos,resultado.extra_minutos),(trabalho,atraso,extra))
                self.assertEqual(extra_bruta(resultado.dados_legados,r,m),extra)
                self.assertEqual(resultado.disponibilidade,"completo")
                self.assertEqual(resultado.dados_legados["saida_almoco"],horarios[1])
        for horarios in (("09:00","12:00",None,"18:00"),("09:00",None,"13:00","18:00")):
            resultado,_,_=self.apurar(horarios,self.regra(registro_intervalo="pre_assinalado"))
            self.assertEqual(resultado.disponibilidade,"incompleto")
            self.assertIsNone(resultado.trabalhados_minutos)

    def test_legado_duas_batidas_nao_vira_preassinalado(self):
        resultado,_,_=self.apurar(("09:00",None,None,"18:00"),self.regra(tipo_intervalo=None,registro_intervalo=None,duracao_intervalo_minutos=None))
        self.assertEqual(resultado.disponibilidade,"incompleto")
        self.assertNotIn("intervalo_aplicado",resultado.dados_legados)

    def test_origens_preassinalacao_distinta_e_evidencia_inalterada(self):
        resultado,m,_=self.apurar(("09:00",None,None,"18:00"),self.regra(registro_intervalo="pre_assinalado"))
        self.assertIsNone(m.saida_almoco)
        self.assertEqual(resultado.dados_legados["origens_horarios_calculo"]["saida_almoco"],"pre_assinalado")
        self.assertEqual(resultado.dados_legados["intervalo_aplicado"]["inicio_previsto"],"12:00")

    def test_flexivel_sem_horario_de_almoco_calcula_duracao(self):
        r=self.regra(tipo_intervalo="flexivel",horario_saida_almoco_prevista=None,horario_retorno_almoco_prevista=None)
        resultado,_,_=self.apurar(("09:00","12:35","13:35","18:00"),r)
        self.assertEqual((resultado.previstos_minutos,resultado.trabalhados_minutos,resultado.atraso_minutos),(480,480,0))

    def test_tolerancias_limites_e_intervalo_sem_dupla_penalizacao(self):
        r=self.regra(tipo_intervalo="flexivel",tolerancia_atraso_minutos=5,tolerancia_extra_minutos=10,tolerancia_intervalo_minutos=0)
        for saida,extra in (("18:10",0),("18:11",11)):
            resultado,m,_=self.apurar(("09:00","12:35","13:35",saida),r)
            self.assertEqual(extra_bruta(resultado.dados_legados,r,m),extra)
        for entrada,saida,atraso in (("09:05","18:05",0),("09:06","18:06",6)):
            self.assertEqual(self.apurar((entrada,"12:35","13:35",saida),r)[0].atraso_minutos,atraso)
        self.assertEqual(self.apurar(("09:00","12:00","13:30","18:00"),r)[0].atraso_minutos,30)

    def test_sem_intervalo_sabado_240_e_feriado_com_batidas(self):
        r=self.regra(tipo_intervalo="sem_intervalo",duracao_intervalo_minutos=0,
            horario_saida_almoco_prevista=None,horario_retorno_almoco_prevista=None,horario_saida_prevista=time(13))
        resultado,_,_=self.apurar(("09:00",None,None,"13:00"),r)
        self.assertEqual((resultado.previstos_minutos,resultado.trabalhados_minutos),(240,240))
        resultado,_,_=self.apurar(("09:00",None,None,"18:00"),self.regra(registro_intervalo="pre_assinalado"),calendario=("FICTÍCIO",))
        self.assertEqual(resultado.dados_legados["horas_feriado_minutos"],480)

    def test_banco_misto_flexivel_sem_extra_ficticia_e_adicional_60(self):
        p={"modo":"misto","percentual_folha":50,"percentual_banco":50,"adicional_folha_percentual":60,
           "ciclo_dias":180,"inicio_ciclo":"2026-09-01"}
        r=self.regra(tipo_intervalo="flexivel",politica_horas=p,usa_banco_horas=True)
        for saida,esperado in (("18:00",(0,0,0)),("19:00",(60,30,30))):
            resultado,m,_=self.apurar(("09:00","12:35","13:35",saida),r)
            d=resultado.para_api_legada()
            distribuir_dia(d,r,m,SimpleNamespace(feriado_entra_banco=False),{})
            self.assertEqual((d["extra_apurada_minutos"],d["extra_folha_minutos"],d["extra_banco_minutos"]),esperado)
            self.assertEqual(d["adicional_folha_percentual"],"60")

    def test_atestado_integral_e_abono_parcial(self):
        integral=Ocorrencia(1,"ATESTADO",date(2026,9,1),date(2026,9,1))
        resultado,_,_=self.apurar((None,None,None,None),self.regra(registro_intervalo="pre_assinalado"),(integral,))
        self.assertEqual((resultado.atraso_minutos,resultado.extra_minutos),(0,0))
        parcial=replace(integral,hora_inicio=time(9),hora_fim=time(10))
        resultado,_,_=self.apurar(("10:00","12:00","13:00","18:00"),ocorrencias=(parcial,))
        self.assertEqual(resultado.dados_legados["minutos_abonados"],60)
        self.assertEqual(resultado.atraso_minutos,0)

    def test_validacao_configuracoes_incoerentes(self):
        base={"empresa_id":1,"nome":"FICTÍCIA","jornada_seg_sex_horas":8}
        for dados in ({"registro_intervalo":"pre_assinalado"},{"tipo_intervalo":"fixo","registro_intervalo":"batidas","duracao_intervalo_minutos":60},
                      {"tipo_intervalo":"sem_intervalo","registro_intervalo":"pre_assinalado"}):
            with self.subTest(dados=dados),self.assertRaises(ValueError): EscalaCreate(**base,**dados)

    def test_abono_parcial_flexivel_nao_abona_deslocamento_de_almoco(self):
        r=self.regra(tipo_intervalo="flexivel")
        o=Ocorrencia(1,"DECLARACAO",date(2026,9,1),date(2026,9,1),time(13),time(13,35))
        d=self.apurar(("09:00","12:35","13:35","18:00"),r,(o,))[0]
        self.assertEqual(d.dados_legados["minutos_abonados"],0)
        self.assertEqual((d.trabalhados_minutos,d.atraso_minutos),(480,0))

    def test_jornada_propria_valida_intervalo_herdado_e_duracao(self):
        base=dict(empresa_id=1,nome="FICTÍCIA",modo_apuracao="horario_fixo",horario_entrada_prevista="09:00",
            horario_saida_prevista="18:00",tipo_intervalo="flexivel",registro_intervalo="batidas",duracao_intervalo_minutos=60)
        diaria=dict(jornada_minutos=480,horario_entrada_prevista="09:00",horario_saida_prevista="18:00")
        self.assertEqual(EscalaCreate(**base,jornadas_semana={"1":diaria}).jornadas_semana["1"].jornada_minutos,480)
        with self.assertRaises(ValueError):
            EscalaCreate(**base,jornadas_semana={"1":dict(diaria,jornada_minutos=540)})
        fixo=dict(base,tipo_intervalo="fixo",horario_saida_almoco_prevista="12:00",horario_retorno_almoco_prevista="13:00")
        with self.assertRaises(ValueError): EscalaCreate(**fixo,jornadas_semana={"5":diaria})
        sabado=dict(jornada_minutos=240,horario_entrada_prevista="08:00",horario_saida_prevista="12:00",
            tipo_intervalo="sem_intervalo",registro_intervalo="batidas",duracao_intervalo_minutos=0)
        self.assertEqual(EscalaCreate(**fixo,jornadas_semana={"5":sabado}).jornadas_semana["5"].jornada_minutos,240)

    def test_horario_corrigido_tem_origem_distinta_da_evidencia(self):
        r=self.regra(registro_intervalo="pre_assinalado")
        _,m,_=self.apurar(("09:00",None,None,"18:00"),r)
        m=replace(m,batidas_originais='["09:00","17:59"]',origem="arquivo")
        resultado=apurar_dia(FuncionarioDoDia(1,"FICTÍCIO",r),m)
        self.assertEqual(resultado.dados_legados["origens_horarios_calculo"],
            {"entrada":"real","saida":"corrigido","saida_almoco":"pre_assinalado","retorno_almoco":"pre_assinalado"})
        self.assertEqual(m.batidas_originais,'["09:00","17:59"]')
