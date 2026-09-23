import sys
import unittest
from datetime import date, time
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database.models import Base, Empresa, Funcionario, Escala, Competencia, MarcacaoPonto
from app.apuracao.service import apurar_competencia
from app.competencias.routes import fechar_competencia
from app.competencias.schemas import FechamentoCompetenciaRequest
from app.ocorrencias.routes import criar
from app.ocorrencias.schemas import OcorrenciaCreate
from app.relatorios.routes import espelho_ponto


class EspelhoPontoTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.empresa = Empresa(nome='Empresa teste', cnpj='12.345.678/0001-90')
        self.db.add(self.empresa); self.db.flush()
        self.escala = Escala(empresa_id=self.empresa.id, nome='Fixa', modo_apuracao='horario_fixo',
            horario_entrada_prevista=time(8), horario_saida_almoco_prevista=time(12),
            horario_retorno_almoco_prevista=time(13), horario_saida_prevista=time(17))
        self.db.add(self.escala); self.db.flush()
        self.funcionario = Funcionario(empresa_id=self.empresa.id, nome='Ana Teste', codigo='007',
                                      cargo='Analista', escala_id=self.escala.id)
        self.competencia = Competencia(empresa_id=self.empresa.id, mes=9, ano=2026)
        self.db.add_all([self.funcionario, self.competencia]); self.db.commit()

    def html(self, **params):
        query = dict(competencia_id=self.competencia.id, funcionario_id=self.funcionario.id)
        query.update(params)
        response = espelho_ponto(**query, db=self.db)
        response.text = response.body.decode('utf-8')
        return response

    def calendario_conferido(self):
        apurar_competencia(self.db, self.competencia.id)
        for m in self.db.query(MarcacaoPonto).all():
            m.status_dia = 'feriado'; m.conferido = True; m.origem = 'manual'
        self.db.commit()

    def dia(self, numero, **kwargs):
        m = self.db.query(MarcacaoPonto).filter_by(funcionario_id=self.funcionario.id,
                data=date(2026, 9, numero)).one()
        for k, v in kwargs.items(): setattr(m, k, v)
        self.db.commit()
        return m

    def fechar(self):
        fechar_competencia(self.competencia.id, FechamentoCompetenciaRequest(confirmar_pendencias=True), self.db)

    def test_dias_variados_totais_filtrados_e_assinaturas(self):
        self.calendario_conferido()
        self.dia(1, status_dia='normal', entrada=time(8,30), saida_almoco=time(12), retorno_almoco=time(13), saida=time(17))
        self.dia(2, status_dia='normal', entrada=time(8), saida_almoco=time(12), retorno_almoco=time(13), saida=time(18))
        self.dia(3, status_dia='falta'); self.dia(4, status_dia='atestado')
        outro = Funcionario(empresa_id=self.empresa.id, nome='Outro trabalhador', escala_id=self.escala.id)
        self.db.add(outro); self.db.flush()
        self.db.add(MarcacaoPonto(competencia_id=self.competencia.id, funcionario_id=outro.id,
            data=date(2026,9,1), status_dia='falta')); self.db.commit()
        response = self.html(); html = response.text
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])
        self.assertEqual(html.count('<tr class="dia">'), 30)
        self.assertIn('<td>01/09/2026</td><td>Ter</td>', html)
        for value in ('Atrasos: <strong>00:30', 'Extras: <strong>01:00', 'Faltas: <strong>1',
                      'Atestados: <strong>1', 'CNPJ: 12.345.678/0001-90', 'Código: 007', 'Analista',
                      'Empresa teste', 'Imprimir / Salvar PDF'):
            self.assertIn(value, html)
        self.assertNotIn('Responsável DP/Contabilidade', html)
        self.assertEqual(html.count('Data: ____/____/________'), 2)
        self.assertNotIn('Outro trabalhador', html)
        self.assertNotIn('documento sujeito a revisão', html)
        resumo = apurar_competencia(self.db, self.competencia.id)['resumo'][0]
        self.assertEqual((resumo['atrasos_minutos'], resumo['extras_minutos']), (30, 60))

    def test_aviso_aberta_e_ausente_quando_fechada(self):
        self.assertIn('documento sujeito a revisão', self.html().text)
        self.fechar()
        self.assertNotIn('documento sujeito a revisão', self.html().text)

    def test_fechada_preserva_html_apos_mudar_escala(self):
        self.calendario_conferido()
        self.dia(1, status_dia='normal', entrada=time(8), saida_almoco=time(12), retorno_almoco=time(13), saida=time(18))
        self.fechar()
        antes = self.html().text
        snapshot = self.competencia.apuracao_fechada
        self.escala.horario_saida_prevista = time(18)
        self.funcionario.nome = 'Nome posterior'; self.funcionario.codigo = '999'
        self.db.commit()
        self.assertEqual(self.html().text, antes)
        self.assertEqual(self.competencia.apuracao_fechada, snapshot)

    def test_404_competencia_funcionario_e_outra_empresa(self):
        empresa = Empresa(nome='Outra empresa'); self.db.add(empresa); self.db.flush()
        funcionario = Funcionario(empresa_id=empresa.id, nome='De fora'); self.db.add(funcionario); self.db.commit()
        for params in (dict(competencia_id=999), dict(funcionario_id=999), dict(funcionario_id=funcionario.id)):
            with self.subTest(params=params), self.assertRaises(HTTPException) as exc:
                self.html(**params)
            self.assertEqual(exc.exception.status_code, 404)

    def test_escapa_cadastro_observacoes_e_ocorrencia(self):
        self.calendario_conferido()
        texto = '<script>alert("teste")</script> & O\'Brien'
        self.funcionario.nome = texto; self.funcionario.cargo = texto; self.funcionario.codigo = texto
        self.empresa.nome = texto; self.empresa.cnpj = texto
        self.dia(1, observacoes=texto)
        html = self.html().text
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;alert(&quot;teste&quot;)&lt;/script&gt; &amp; O&#x27;Brien', html)

    def test_ocorrencias_e_abonos_individuais(self):
        self.calendario_conferido()
        self.dia(1, status_dia='normal', entrada=time(8), saida_almoco=time(12), retorno_almoco=time(15), saida=time(17))
        criar(OcorrenciaCreate(funcionario_id=self.funcionario.id, tipo='DECLARACAO', data_inicio=date(2026,9,1),
                              data_fim=date(2026,9,1), hora_inicio=time(13), hora_fim=time(15)), self.db)
        html = self.html().text
        self.assertIn('<td>DECLARAÇÃO</td><td>120</td>', html)
        self.assertIn('Dias com ocorrência: <strong>1', html)
        self.assertIn('Atrasos: <strong>00:00', html)

    def test_inativo_sem_marcacoes_nao_inventa_dias_ou_totais(self):
        self.funcionario.ativo = False; self.db.commit()
        html = self.html().text
        self.assertIn('Sem marcações disponíveis', html)
        self.assertIn('Atrasos: <strong>Indisponível', html)
        self.assertEqual(self.db.query(MarcacaoPonto).count(), 0)

    def test_todos_pendentes_nao_publica_totais_zerados_como_validos(self):
        self.html()
        for m in self.db.query(MarcacaoPonto).all():
            m.status_dia = 'normal'; m.conferido = False; m.origem = 'manual'
        self.db.commit()
        html = self.html().text
        self.assertEqual(html.count('<tr class="dia">'), 30)
        self.assertIn('Atrasos: <strong>Indisponível', html)
        self.assertIn('Extras: <strong>Indisponível', html)
        self.assertIn('documento sujeito a revisão', html)
        self.fechar()
        fechado = self.html().text
        self.assertNotIn('documento sujeito a revisão', fechado)
        self.assertIn('Entrada ou saída não informada.', fechado)
        self.assertIn('Atrasos: <strong>Indisponível', fechado)

    def test_transferencia_com_marcacoes_bloqueada_preserva_espelho(self):
        from app.funcionarios.routes import atualizar_funcionario
        from app.funcionarios.schemas import FuncionarioUpdate
        self.calendario_conferido()
        antes = self.html().text
        destino = Empresa(nome='Destino'); self.db.add(destino); self.db.commit()
        with self.assertRaises(HTTPException) as exc:
            atualizar_funcionario(self.funcionario.id,
                FuncionarioUpdate(empresa_id=destino.id, escala_id=None), self.db)
        self.assertEqual(exc.exception.status_code, 409)
        self.db.rollback()
        self.assertEqual(self.html().text, antes)

    def test_transferencia_sem_historico_continua_permitida(self):
        from app.funcionarios.routes import atualizar_funcionario
        from app.funcionarios.schemas import FuncionarioUpdate
        destino = Empresa(nome='Destino'); self.db.add(destino); self.db.commit()
        atualizar_funcionario(self.funcionario.id,
            FuncionarioUpdate(empresa_id=destino.id, escala_id=None), self.db)
        self.assertEqual(self.funcionario.empresa_id, destino.id)

    def test_declaracao_sem_abono_preserva_tolerancia_e_espelho(self):
        self.calendario_conferido()
        self.escala.tolerancia_intervalo_minutos = 10; self.db.commit()
        self.dia(1, status_dia='normal', entrada=time(8), saida_almoco=time(12), retorno_almoco=time(13,5), saida=time(17,5))
        self.assertIn('Atrasos: <strong>00:00', self.html().text)
        criar(OcorrenciaCreate(funcionario_id=self.funcionario.id, tipo='DECLARACAO', data_inicio=date(2026,9,1),
                              data_fim=date(2026,9,1), hora_inicio=time(18), hora_fim=time(19)), self.db)
        self.assertIn('Atrasos: <strong>00:00', self.html().text)

    def test_abono_zero_nao_esconde_conflito_com_situacao_manual(self):
        self.calendario_conferido()
        self.dia(1, status_dia='falta', entrada=time(8), saida_almoco=time(12), retorno_almoco=time(13), saida=time(17))
        criar(OcorrenciaCreate(funcionario_id=self.funcionario.id, tipo='DECLARACAO', data_inicio=date(2026,9,1),
                              data_fim=date(2026,9,1), hora_inicio=time(18), hora_fim=time(19)), self.db)
        self.assertIn('Ocorrência parcial com situação manual diferente de normal', self.html().text)

    def test_abono_efetivo_nao_aumenta_atraso_ja_tolerado(self):
        self.calendario_conferido()
        self.escala.tolerancia_intervalo_minutos = 10; self.db.commit()
        self.dia(1, status_dia='normal', entrada=time(8), saida_almoco=time(12), retorno_almoco=time(13,5), saida=time(17,5))
        criar(OcorrenciaCreate(funcionario_id=self.funcionario.id, tipo='DECLARACAO', data_inicio=date(2026,9,1),
                              data_fim=date(2026,9,1), hora_inicio=time(13), hora_fim=time(13,1)), self.db)
        detalhe = apurar_competencia(self.db, self.competencia.id)['marcacoes'][0]
        self.assertEqual(detalhe['minutos_abonados'], 1)
        self.assertEqual(detalhe['atraso_minutos'], 0)

    def test_detector_importacao_calendario_ocorrencia_e_fechamento(self):
        from io import BytesIO
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from fastapi import UploadFile
        from app.importadores.routes import analisar_importacao, confirmar_importacao
        from app.importadores.schemas import ConfirmacaoImportacao
        from app.database.models import ArquivoRecebido
        self.html()  # Gera placeholders reais antes da importação.
        criar(OcorrenciaCreate(funcionario_id=self.funcionario.id, tipo='DECLARACAO', data_inicio=date(2026,9,1),
                              data_fim=date(2026,9,1), hora_inicio=time(13), hora_fim=time(15)), self.db)
        txt = 'ID\tNome\tDepart.\tTempo\tNúmero da máquina\t\n' + ''.join(
            f'007\tAna Teste\tDP\t 01/09/2026     {hora}\t1\n'
            for hora in ('08:00:00', '12:00:00', '15:00:00', '17:00:00'))
        with TemporaryDirectory() as pasta, patch('app.importadores.routes.UPLOADS_DIR', Path(pasta)):
            analise = analisar_importacao(self.competencia.id, self.empresa.id, 9, 2026,
                    UploadFile(filename='relogio.txt', file=BytesIO(txt.encode('utf-8'))), self.db)
            self.assertEqual(analise['tipo_detectado'], 'txt_id_tempo_maquina')
            payload = ConfirmacaoImportacao(empresa_id=self.empresa.id, competencia_id=self.competencia.id,
                    arquivo_id=analise['arquivo']['id'], registros_ids=[analise['preview'][0]['id']])
            resultado = confirmar_importacao(payload, self.db)
            self.assertEqual(resultado['total_importados'], 1)
            m = self.db.get(MarcacaoPonto, resultado['marcacoes_ids'][0])
            original = m.batidas_originais
            self.assertIn('<td>DECLARAÇÃO</td><td>120</td>', self.html().text)
            self.assertEqual(confirmar_importacao(payload, self.db)['total_importados'], 0)
            self.fechar(); html = self.html().text
            arquivo_count = self.db.query(ArquivoRecebido).count()
            with self.assertRaises(HTTPException) as exc:
                confirmar_importacao(payload, self.db)
            self.assertEqual(exc.exception.status_code, 409)
            with self.assertRaises(HTTPException) as exc:
                analisar_importacao(self.competencia.id, self.empresa.id, 9, 2026,
                    UploadFile(filename='outro.txt', file=BytesIO(txt.encode('utf-8'))), self.db)
            self.assertEqual(exc.exception.status_code, 409)
            self.assertEqual(self.db.query(ArquivoRecebido).count(), arquivo_count)
            self.assertEqual(m.batidas_originais, original)
            self.assertEqual(self.html().text, html)


if __name__ == '__main__':
    unittest.main()
