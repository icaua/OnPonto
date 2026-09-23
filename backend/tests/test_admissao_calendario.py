import json
import sys
import unittest
from datetime import date, time
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.apuracao.service import apurar_competencia, detalhe_marcacao, gerar_dias_faltantes
from app.calendario.service import data_no_ano, dentro_periodo
from app.database.models import Base, Empresa, Escala, Funcionario, Competencia, EventoCalendario, MarcacaoPonto, OcorrenciaFuncionario
from app.database.migrations import aplicar_migracoes_compativeis, SCHEMA_VERSION


class AdmissaoCalendarioTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False)
        self.empresa = Empresa(nome='Empresa teste', cidade='São Paulo', uf='SP')
        self.db.add(self.empresa)
        self.db.flush()
        self.escala = Escala(empresa_id=self.empresa.id, nome='Padrão', modo_apuracao='carga_horaria',
            jornada_seg_sex_horas=8, jornada_sabado_horas=4, regime_sabado='nao_trabalha', regime_domingo='nao_trabalha')
        self.db.add(self.escala)
        self.db.flush()
        self.f = Funcionario(empresa_id=self.empresa.id, nome='Pessoa', codigo='1', escala_id=self.escala.id)
        self.c = Competencia(empresa_id=self.empresa.id, mes=6, ano=2026)
        self.db.add_all([self.f, self.c])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def apurar(self, **kwargs):
        self.db.flush()
        return apurar_competencia(self.db, self.c.id, **kwargs)

    def evento(self, **kwargs):
        evento = EventoCalendario(**dict(dict(nome='Feriado teste', data=date(2026,6,18),
            tipo='FERIADO', abrangencia='NACIONAL', recorrente=False, ativo=True), **kwargs))
        self.db.add(evento)
        self.db.flush()
        return evento

    def batida(self, **kwargs):
        m = MarcacaoPonto(**dict(dict(competencia_id=self.c.id, funcionario_id=self.f.id,
            data=date(2026,6,15), entrada=time(8,2), origem='importacao',
            batidas_originais='["08:02"]', conferido=False), **kwargs))
        self.db.add(m)
        self.db.flush()
        return m

    def dia(self, resultado, dia=18):
        return next(m for m in resultado['marcacoes'] if m['data'] == f'2026-06-{dia:02}')

    def test_a_admissao_primeiro_dia_processa_mes_inteiro(self):
        self.f.data_admissao = date(2026,6,1)
        r = self.apurar()
        self.assertEqual(r['resumo'][0]['dias_processados'],30)
        self.assertEqual(len(r['marcacoes']),30)

    def test_b_admissao_dia_18_processa_13_dias(self):
        self.f.data_admissao = date(2026,6,18)
        r = self.apurar()
        self.assertEqual(r['resumo'][0]['dias_processados'],13)
        self.assertEqual(len(r['marcacoes']),13)
        self.assertTrue(all(m['data'] >= '2026-06-18' for m in r['pendencias']))
        self.assertEqual(self.db.query(MarcacaoPonto).count(),13)

    def test_c_admissao_julho_junho_zerado_sem_dias(self):
        self.f.data_admissao = date(2026,7,10)
        r = self.apurar()
        self.assertEqual(r['marcacoes'],[])
        self.assertEqual(r['pendencias'],[])
        self.assertEqual(r['resumo'][0]['situacao'],'fora_vinculo')
        for campo in ['dias_processados','faltas','atestados','pendencias','atrasos_minutos','extras_minutos']:
            self.assertEqual(r['resumo'][0][campo],0, campo)
        self.assertIsNotNone(self.db.get(Funcionario,self.f.id))

    def test_d_batida_anterior_preservada_avisada_sem_jornada(self):
        self.f.data_admissao = date(2026,6,18)
        m = self.batida()
        r = self.apurar()
        detalhe = self.dia(r,15)
        self.assertEqual(detalhe['pendencia_motivo'],'Marcação anterior à data de admissão')
        self.assertEqual(detalhe['entrada'],'08:02')
        for campo in ['jornada_prevista_minutos','horas_trabalhadas_minutos','atraso_minutos','extra_minutos','falta']:
            self.assertEqual(detalhe[campo],0,campo)
        self.assertEqual(r['resumo'][0]['dias_processados'],13)
        self.assertEqual(m.batidas_originais,'["08:02"]')
        self.assertEqual(m.status_dia,'normal')

    def test_e_admissao_nula_preserva_comportamento(self):
        r = self.apurar()
        self.assertEqual(r['resumo'][0]['dias_processados'],30)
        self.assertIsNone(self.f.data_admissao)
        self.assertEqual(self.dia(r)['jornada_prevista_minutos'],480)

    def test_editar_admissao_remove_so_placeholders_intocados(self):
        m = self.batida(data=date(2026,6,16))
        self.apurar()
        manual = self.db.query(MarcacaoPonto).filter_by(data=date(2026,6,15)).one()
        manual.status_dia = 'falta'
        manual.conferido = True
        self.f.data_admissao = date(2026,6,18)
        r = self.apurar()
        self.assertEqual(r['resumo'][0]['dias_processados'],13)
        self.assertEqual(r['resumo'][0]['faltas'],0)
        self.assertIsNotNone(self.db.get(MarcacaoPonto, m.id))
        self.assertEqual(manual.status_dia,'falta')
        self.assertEqual(self.db.query(MarcacaoPonto).count(),15)
        self.f.data_admissao = None
        self.assertEqual(self.apurar()['resumo'][0]['dias_processados'],30)

    def test_apuracao_sem_gerar_tambem_exclui_placeholders_antigos(self):
        self.apurar()
        self.f.data_admissao = date(2026,6,18)
        r = self.apurar(gerar_calendario=False)
        self.assertEqual(len(r['marcacoes']),13)
        self.assertEqual(r['resumo'][0]['dias_processados'],13)

    def test_dia_sem_batidas_com_historico_humano_nao_eh_apagado(self):
        self.apurar()
        m = self.db.query(MarcacaoPonto).filter_by(data=date(2026,6,15)).one()
        m.historico_json = '[{"descricao":"Observação removida pelo usuário"}]'
        self.f.data_admissao = date(2026,6,18)
        r = self.apurar()
        self.assertIsNotNone(self.db.get(MarcacaoPonto,m.id))
        self.assertEqual(self.dia(r,15)['status_dia'],'fora_vinculo')
        self.assertFalse(self.dia(r,15)['pendente'])
        self.assertEqual(r['resumo'][0]['dias_processados'],13)

    def test_verificacao_vinculo_antes_escala_feriado_ocorrencia(self):
        self.f.data_admissao = date(2026,6,18)
        self.f.escala = None
        m = self.batida()
        self.evento(data=m.data)
        self.db.add(OcorrenciaFuncionario(funcionario_id=self.f.id,
            tipo='ATESTADO',data_inicio=m.data,data_fim=m.data))
        r = self.apurar()
        d = self.dia(r,15)
        self.assertEqual(d['pendencia_tipo'],'marcacao_anterior_admissao')
        self.assertFalse(d['pendente_calculo'])
        self.assertEqual(d['atestado'],0)
        self.assertEqual(d['feriados'],[])

    def test_batida_antes_vinculo_futuro_mantem_pendencia_real(self):
        self.f.data_admissao = date(2026,7,10)
        self.batida(conferido=True)
        r = self.apurar()
        self.assertEqual(r['resumo'][0]['dias_processados'],0)
        self.assertEqual(r['resumo'][0]['pendencias'],1)
        self.assertEqual(r['resumo'][0]['situacao'],'pendente')

    def test_feriado_nacional_aplica_sem_gravar_status(self):
        self.evento()
        d = self.dia(self.apurar())
        self.assertEqual(d['status_dia'],'feriado')
        self.assertFalse(d['pendente'])
        self.assertEqual(d['atraso_minutos'],0)
        original = self.db.query(MarcacaoPonto).filter_by(data=date(2026,6,18)).one()
        self.assertEqual(original.status_dia,'normal')
        self.assertFalse(original.conferido)

    def test_feriado_estadual_somente_uf_correta(self):
        e = self.evento(abrangencia='ESTADUAL',uf='RJ')
        self.assertEqual(self.dia(self.apurar())['status_dia'],'normal')
        e.uf = 'SP'
        self.assertEqual(self.dia(self.apurar())['status_dia'],'feriado')

    def test_feriado_municipal_compara_cidade_e_uf(self):
        e = self.evento(abrangencia='MUNICIPAL',uf='SP',municipio='Campinas')
        self.assertEqual(self.dia(self.apurar())['status_dia'],'normal')
        e.municipio = '  SAO  PAULO '
        self.assertEqual(self.dia(self.apurar())['status_dia'],'feriado')
        e.uf = 'RJ'
        self.assertEqual(self.dia(self.apurar())['status_dia'],'normal')

    def test_feriado_empresa_nao_vaza_para_outra(self):
        outra = Empresa(nome='Outra')
        self.db.add(outra)
        self.db.flush()
        e = self.evento(abrangencia='EMPRESA',empresa_id=outra.id)
        self.assertEqual(self.dia(self.apurar())['status_dia'],'normal')
        e.empresa_id = self.empresa.id
        self.assertEqual(self.dia(self.apurar())['status_dia'],'feriado')

    def test_comemorativa_inativa_outro_ano_ou_mes_nao_afetam(self):
        self.evento(tipo='DATA_COMEMORATIVA')
        self.evento(ativo=False)
        self.evento(data=date(2025,6,18))
        self.evento(data=date(2026,7,18))
        self.assertEqual(self.dia(self.apurar())['status_dia'],'normal')

    def test_recorrencia_fixa_e_bissexto(self):
        e = self.evento(data=date(2025,6,18),recorrente=True)
        self.assertEqual(self.dia(self.apurar())['status_dia'],'feriado')
        e.data = date(2024,2,29)
        self.assertIsNone(data_no_ano(e,2026))
        self.assertEqual(data_no_ano(e,2028),date(2028,2,29))

    def test_desativar_e_editar_feriado_recalcula_competencia_aberta(self):
        e = self.evento()
        self.assertFalse(self.dia(self.apurar())['pendente'])
        e.ativo = False
        self.assertTrue(self.dia(self.apurar())['pendente'])
        e.ativo = True
        e.data = date(2026,6,19)
        self.assertEqual(self.dia(self.apurar(),18)['status_dia'],'normal')
        self.assertEqual(self.dia(self.apurar(),19)['status_dia'],'feriado')

    def test_feriado_preserva_regra_atual_e_decisao_manual(self):
        e = self.evento()
        m = self.batida(data=e.data,saida=time(19),conferido=True)
        manual = detalhe_marcacao(self.f,m)
        m.status_dia = 'feriado'
        esperado = detalhe_marcacao(self.f,m)
        m.status_dia = 'normal'
        atual = self.dia(self.apurar())
        self.assertGreater(manual['extra_minutos'],0)
        for campo in ['atraso_minutos','extra_minutos','horas_trabalhadas_minutos','jornada_prevista_minutos']:
            self.assertEqual(atual[campo],esperado[campo])
        m.status_dia = 'atestado'
        self.assertEqual(self.dia(self.apurar())['status_dia'],'atestado')

    def test_fechada_preserva_snapshot_apos_editar_admissao_e_evento(self):
        e = self.evento()
        snapshot = self.apurar()
        snapshot['competencia']['status'] = 'fechada'
        self.c.status = 'fechada'
        self.c.apuracao_fechada = json.dumps(snapshot)
        ids = [m.id for m in self.db.query(MarcacaoPonto).all()]
        self.f.data_admissao = date(2026,7,10)
        e.ativo = False
        self.assertEqual(self.apurar(),snapshot)
        self.assertEqual(gerar_dias_faltantes(self.db,self.c),0)
        self.assertEqual([m.id for m in self.db.query(MarcacaoPonto).all()],ids)

    def test_predicado_periodo_permite_futuro_limite_final(self):
        self.assertTrue(dentro_periodo(date(2026,6,18),date(2026,6,18),date(2026,6,18)))
        self.assertFalse(dentro_periodo(date(2026,6,19),date(2026,6,18),date(2026,6,18)))

    def test_migracao_6_para_7_preserva_dados_e_eh_idempotente(self):
        self.db.close()
        with self.engine.begin() as c:
            c.exec_driver_sql('DROP TABLE eventos_calendario')
            c.exec_driver_sql('ALTER TABLE funcionarios DROP COLUMN data_admissao')
            c.exec_driver_sql('PRAGMA user_version = 6')
        aplicar_migracoes_compativeis(self.engine)
        aplicar_migracoes_compativeis(self.engine)
        with self.engine.connect() as c:
            self.assertEqual(c.exec_driver_sql('SELECT nome, data_admissao FROM funcionarios').one(),('Pessoa',None))
            self.assertEqual(c.exec_driver_sql('SELECT count(*) FROM eventos_calendario').scalar_one(),0)
            self.assertEqual(c.exec_driver_sql('PRAGMA user_version').scalar_one(),SCHEMA_VERSION)
            self.assertEqual(c.exec_driver_sql('PRAGMA foreign_key_check').all(),[])
