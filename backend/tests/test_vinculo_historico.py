"""Regressões P0 com SQLite em memória e pessoas fictícias."""
from datetime import date, time
import json
import unittest

import test_admissao_calendario as fixture
from fastapi import HTTPException
from app.apuracao.service import apurar_competencia, gerar_dias_faltantes
from app.apuracao.triagem import consultar_triagem
from app.competencias.routes import fechar_competencia, inicializar_calendario
from app.competencias.schemas import FechamentoCompetenciaRequest
from app.competencias.service import sincronizar_status_competencia
from app.database.models import (ArquivoRecebido, FechamentoVersao, Funcionario,
    HistoricoVinculoEscala, MarcacaoPonto, Escala)
from app.funcionarios.routes import atualizar_funcionario
from app.funcionarios.schemas import FuncionarioUpdate


class VinculoHistoricoTest(unittest.TestCase):
    setUp = fixture.AdmissaoCalendarioTest.setUp
    tearDown = fixture.AdmissaoCalendarioTest.tearDown

    def vinculo(self, inicio, fim, ativo=False):
        self.f.ativo = ativo
        self.f.data_admissao = inicio
        self.f.data_demissao = fim
        self.db.commit()

    def resultado(self):
        return apurar_competencia(self.db, self.c.id)

    def test_inativo_admitido_e_desligado_no_mes_inclusivo_idempotente(self):
        self.vinculo(date(2026, 6, 10), date(2026, 6, 15))
        self.assertEqual(self.resultado()['operacional']['dias_sem_registro'], 6)
        self.assertEqual(gerar_dias_faltantes(self.db, self.c), 6)
        ids = [m.id for m in self.db.query(MarcacaoPonto).order_by(MarcacaoPonto.data)]
        self.assertEqual(gerar_dias_faltantes(self.db, self.c), 0)
        self.assertEqual([m.id for m in self.db.query(MarcacaoPonto).order_by(MarcacaoPonto.data)], ids)
        r = self.resultado()
        self.assertEqual([m['data'] for m in r['marcacoes']], [f'2026-06-{d:02d}' for d in range(10, 16)])
        self.assertGreater(r['operacional']['problemas'], 0)
        self.assertFalse(r['fechamento']['pode_fechar'])
        self.assertEqual(self.f.data_admissao, date(2026, 6, 10))
        self.assertEqual(self.f.data_demissao, date(2026, 6, 15))

    def test_inativo_cobre_competencia_anterior_inteira(self):
        self.vinculo(date(2025, 1, 1), date(2026, 9, 15))
        self.assertEqual(self.resultado()['operacional']['dias_sem_registro'], 30)
        self.assertEqual(gerar_dias_faltantes(self.db, self.c), 30)
        self.assertEqual(self.resultado()['resumo'][0]['dias_processados'], 30)

    def test_limites_e_vinculos_sem_intersecao(self):
        for ativo in (True, False):
            for inicio, fim, quantidade in (
                (date(2026, 6, 18), date(2026, 7, 1), 13),
                (date(2026, 5, 1), date(2026, 6, 15), 15),
                (date(2026, 7, 1), date(2026, 7, 31), 0),
                (date(2026, 5, 1), date(2026, 5, 31), 0),
            ):
                with self.subTest(ativo=ativo, inicio=inicio, fim=fim):
                    self.db.query(MarcacaoPonto).delete()
                    self.vinculo(inicio, fim, ativo)
                    self.assertEqual(self.resultado()['operacional']['dias_sem_registro'], quantidade)
                    self.assertEqual(gerar_dias_faltantes(self.db, self.c), quantidade)

    def test_importado_e_decisao_humana_preservados_inclusive_fora_vinculo(self):
        self.vinculo(date(2026, 6, 10), date(2026, 6, 15))
        a = ArquivoRecebido(competencia_id=self.c.id, nome_original='ficticio.txt',
            tipo_arquivo='txt', caminho_arquivo='uploads/ficticio.txt', sha256='a'*64)
        self.db.add(a)
        self.db.flush()
        for dia in (9, 10, 16):
            self.db.add(MarcacaoPonto(competencia_id=self.c.id, funcionario_id=self.f.id,
                data=date(2026, 6, dia), entrada=time(8), saida=time(17),
                origem='txt_generico', arquivo_origem_id=a.id,
                batidas_originais='["08:00", "08:00", "17:00"]',
                historico_json='[{"descricao":"Decisão fictícia"}]', observacoes='Preservar'))
        self.db.commit()
        def originais():
            return [{col.name: getattr(m, col.name) for col in MarcacaoPonto.__table__.columns}
                for m in self.db.query(MarcacaoPonto).filter_by(arquivo_origem_id=a.id).order_by(MarcacaoPonto.id)]
        antes = originais()
        self.assertEqual(gerar_dias_faltantes(self.db, self.c), 5)
        self.assertEqual(gerar_dias_faltantes(self.db, self.c), 0)
        self.assertEqual(originais(), antes)
        self.assertEqual(self.db.query(MarcacaoPonto).count(), 8)

    def test_escala_historica_prevalece_sobre_cadastro_atual(self):
        self.vinculo(date(2026, 6, 1), date(2026, 6, 30))
        atual = Escala(empresa_id=self.empresa.id, nome='Atual fictícia', regime_sabado='normal', jornada_sabado_horas=8)
        self.db.add(atual)
        self.db.flush()
        self.db.add(HistoricoVinculoEscala(funcionario_id=self.f.id, escala_id=self.escala.id,
            vigente_desde=date(2026, 1, 1), vigente_ate=date(2026, 6, 30)))
        self.db.add(HistoricoVinculoEscala(funcionario_id=self.f.id, escala_id=atual.id,
            vigente_desde=date(2026, 7, 1)))
        self.f.escala_id = atual.id
        self.db.commit()
        self.assertEqual(gerar_dias_faltantes(self.db, self.c), 30)
        sabado = self.db.query(MarcacaoPonto).filter_by(data=date(2026, 6, 6)).one()
        self.assertEqual((sabado.status_dia, sabado.conferido), ('sem_expediente', True))

    def test_fechamento_bloqueia_lacunas_e_permite_apos_regularizar(self):
        self.vinculo(date(2026, 6, 10), date(2026, 6, 15))
        self.db.add(MarcacaoPonto(competencia_id=self.c.id, funcionario_id=self.f.id,
            data=date(2026, 6, 10), status_dia='folga', conferido=True))
        self.db.commit()
        r = self.resultado()
        triagem = consultar_triagem(self.db, self.c.id)
        self.assertEqual(r['operacional'], triagem['operacional'])
        self.assertEqual(r['operacional']['dias_sem_registro'], 5)
        with self.assertRaises(HTTPException) as erro:
            fechar_competencia(self.c.id, FechamentoCompetenciaRequest(), self.db)
        self.assertEqual(erro.exception.status_code, 409)
        self.assertIn('5 dia(s) do vínculo sem registro', erro.exception.detail['mensagem'])
        self.assertEqual(self.db.query(FechamentoVersao).count(), 0)
        self.assertEqual(inicializar_calendario(self.c.id, self.db)['criados'], 5)
        for m in self.db.query(MarcacaoPonto):
            m.status_dia, m.conferido = 'folga', True
        self.db.commit()
        fechar_competencia(self.c.id, FechamentoCompetenciaRequest(), self.db)
        self.assertEqual(self.c.status, 'fechada')
        snapshot = self.c.apuracao_fechada
        versao = self.db.query(FechamentoVersao).one().snapshot
        linhas = [(m.id, m.status_dia, m.conferido, m.batidas_originais, m.revisao)
                  for m in self.db.query(MarcacaoPonto).order_by(MarcacaoPonto.id)]
        self.f.data_demissao = date(2026, 6, 30)
        self.db.commit()
        self.assertEqual(gerar_dias_faltantes(self.db, self.c), 0)
        self.assertEqual(self.resultado(), json.loads(snapshot))
        self.assertEqual(self.c.apuracao_fechada, snapshot)
        self.assertEqual(self.db.query(FechamentoVersao).one().snapshot, versao)
        self.assertEqual([(m.id, m.status_dia, m.conferido, m.batidas_originais, m.revisao)
                          for m in self.db.query(MarcacaoPonto).order_by(MarcacaoPonto.id)], linhas)

    def test_inativacao_cadastral_nao_esconde_lacunas_nem_status(self):
        self.vinculo(date(2026, 6, 10), date(2026, 6, 15), ativo=True)
        self.db.add(MarcacaoPonto(competencia_id=self.c.id, funcionario_id=self.f.id,
            data=date(2026, 6, 10), status_dia='folga', conferido=True))
        self.db.commit()
        atualizar_funcionario(self.f.id, FuncionarioUpdate(ativo=False), self.db)
        self.assertEqual(self.c.status, 'em_conferencia')
        self.assertEqual(self.resultado()['operacional']['dias_sem_registro'], 5)

    def test_fechada_preserva_snapshot_e_todas_as_linhas(self):
        self.vinculo(date(2026, 6, 10), date(2026, 6, 15))
        # Simula um snapshot legado já fechado com lacunas: não o corrige retroativamente.
        snapshot = self.resultado()
        snapshot.update(snapshot_versao=2)
        snapshot['competencia']['status'] = 'fechada'
        self.c.status = 'fechada'
        self.c.apuracao_fechada = json.dumps(snapshot, ensure_ascii=False)
        self.db.commit()
        antes = self.c.apuracao_fechada
        self.assertEqual(gerar_dias_faltantes(self.db, self.c), 0)
        self.assertEqual(self.resultado(), snapshot)
        self.assertEqual(consultar_triagem(self.db, self.c.id)['operacional'], snapshot['operacional'])
        self.assertEqual(self.db.query(MarcacaoPonto).count(), 0)
        self.assertEqual(self.c.apuracao_fechada, antes)

    def test_legado_inativo_incompleto_nao_inventa_dias_e_explicita_incerteza(self):
        for inicio, fim in ((None, None), (date(2026, 6, 10), None), (None, date(2026, 6, 15))):
            with self.subTest(inicio=inicio, fim=fim):
                self.vinculo(inicio, fim)
                self.assertEqual(gerar_dias_faltantes(self.db, self.c), 0)
                r = self.resultado()
                self.assertEqual(r['operacional']['dias_sem_registro'], 0)
                self.assertEqual(r['avisos_vinculo'][0]['codigo'], 'vinculo_historico_incompleto')
                self.assertIn('Vínculo histórico incompleto', r['resumo'][0]['observacoes'])
                self.assertEqual((self.f.data_admissao, self.f.data_demissao), (inicio, fim))
                self.assertEqual(r['operacional'], consultar_triagem(self.db, self.c.id)['operacional'])

    def test_legado_ativo_sem_datas_mantem_calendario(self):
        self.vinculo(None, None, ativo=True)
        self.assertEqual(gerar_dias_faltantes(self.db, self.c), 30)
        self.assertEqual(self.resultado()['operacional']['dias_sem_registro'], 0)
        self.assertNotIn('avisos_vinculo', self.resultado())

    def test_legado_incompleto_preserva_evidencia_e_fechamento_com_aviso(self):
        self.vinculo(None, date(2026, 6, 15))
        m = MarcacaoPonto(competencia_id=self.c.id, funcionario_id=self.f.id, data=date(2026, 6, 10),
            origem='txt_generico', entrada=time(8), saida_almoco=time(12), retorno_almoco=time(13),
            saida=time(17), batidas_originais='["08:00", "12:00", "13:00", "17:00"]', conferido=True)
        self.db.add(m)
        self.db.commit()
        original = (m.id, m.entrada, m.saida, m.batidas_originais, m.origem, m.revisao)
        self.assertEqual(gerar_dias_faltantes(self.db, self.c), 0)
        sincronizar_status_competencia(self.db, self.c)
        self.assertEqual(self.c.status, 'conferida')
        self.db.commit()
        r = self.resultado()
        self.assertTrue(r['fechamento']['pode_fechar'])
        self.assertEqual(r['avisos_vinculo'][0]['funcionario_id'], self.f.id)
        self.assertEqual((m.id, m.entrada, m.saida, m.batidas_originais, m.origem, m.revisao), original)
        fechar_competencia(self.c.id, FechamentoCompetenciaRequest(), self.db)
        self.assertEqual(self.c.status, 'fechada')
        self.assertEqual(json.loads(self.c.apuracao_fechada)['avisos_vinculo'], r['avisos_vinculo'])

    def test_limite_conhecido_exclui_legado_incompleto_fora_do_periodo(self):
        self.vinculo(date(2026, 6, 1), date(2026, 6, 1))
        for inicio, fim in ((date(2026, 7, 1), None), (None, date(2026, 5, 31))):
            self.db.add(Funcionario(empresa_id=self.empresa.id, nome='Legado fictício fora do período',
                ativo=False, data_admissao=inicio, data_demissao=fim))
        self.db.commit()
        self.assertEqual(gerar_dias_faltantes(self.db, self.c), 1)
        m = self.db.query(MarcacaoPonto).one()
        m.status_dia, m.conferido = 'folga', True
        self.db.commit()
        self.assertTrue(self.resultado()['fechamento']['pode_fechar'])
        self.assertNotIn('avisos_vinculo', self.resultado())
