import re
import unittest
from datetime import date, time
from unittest.mock import patch

import test_espelho_ponto as fixtures
from app.database.models import Funcionario, MarcacaoPonto
from app.relatorios import routes
from app.ocorrencias.routes import criar
from app.ocorrencias.schemas import OcorrenciaCreate


def blocos(html):
    return re.findall(r'<article class="espelho-pagina".*?</article>', html, re.S)


class EspelhoLoteTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.EspelhoPontoTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.db = self.fixture.db
        self.competencia = self.fixture.competencia

    def lote(self):
        return routes.espelho_ponto_lote(self.competencia.id, self.db).body.decode('utf-8')

    def adicionar(self, nome, ativo=True):
        f = Funcionario(empresa_id=self.fixture.empresa.id, nome=nome, ativo=ativo,
                        escala_id=self.fixture.escala.id, cargo='Auxiliar')
        self.db.add(f)
        self.db.commit()
        return f

    def test_lote_apura_uma_vez_e_tres_blocos_identicos_ao_individual(self):
        outro = self.adicionar('Bruno <Teste>')
        inativo = self.adicionar('Carlos sem marcações', ativo=False)
        self.fixture.calendario_conferido()
        self.fixture.dia(1, status_dia='normal', entrada=time(8), saida_almoco=time(12),
                         retorno_almoco=time(15), saida=time(17))
        self.fixture.dia(2, status_dia='falta')
        self.fixture.dia(3, status_dia='atestado')
        criar(OcorrenciaCreate(funcionario_id=self.fixture.funcionario.id, tipo='DECLARACAO',
              data_inicio=date(2026, 9, 1), data_fim=date(2026, 9, 1),
              hora_inicio=time(13), hora_fim=time(15)), self.db)
        with patch.object(routes, 'apurar_competencia', wraps=routes.apurar_competencia) as apurar:
            html = self.lote()
            apurar.assert_called_once_with(self.db, self.competencia.id)
        partes = blocos(html)
        self.assertEqual(len(partes), 3)
        for f in (self.fixture.funcionario, outro, inativo):
            individual = self.fixture.html(funcionario_id=f.id).text
            self.assertIn(blocos(individual)[0], partes)
        self.assertIn('Sem marcações disponíveis para este funcionário nesta competência.', html)
        self.assertIn('Bruno &lt;Teste&gt;', html)
        self.assertIn('.espelho-pagina:not(:last-child) { break-after:page; page-break-after:always; }', html)
        self.assertEqual(html.count('<html '), 1)
        self.assertEqual(html.count('<body>'), 1)
        self.assertEqual(html.count('Data: ____/____/________'), 6)

    def test_competencia_vazia_tem_mensagem_e_inexistente_404(self):
        self.db.delete(self.fixture.funcionario)
        self.db.commit()
        response = routes.espelho_ponto_lote(self.competencia.id, self.db)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Nenhum funcionário disponível nesta competência.', response.body.decode())
        self.assertEqual(blocos(response.body.decode()), [])
        with self.assertRaises(fixtures.HTTPException) as exc:
            routes.espelho_ponto_lote(999, self.db)
        self.assertEqual(exc.exception.status_code, 404)

    def test_lote_fechado_preserva_snapshot_e_lista_original(self):
        self.adicionar('Bruno')
        self.adicionar('Carlos', ativo=False)
        self.fixture.calendario_conferido()
        self.fixture.dia(1, status_dia='normal', entrada=time(8), saida_almoco=time(12),
                         retorno_almoco=time(13), saida=time(18))
        self.fixture.fechar()
        antes = self.lote()
        snapshot = self.competencia.apuracao_fechada
        self.fixture.escala.horario_saida_prevista = time(18)
        self.fixture.escala.tolerancia_intervalo_minutos = 30
        self.fixture.funcionario.nome = 'Nome posterior'
        self.fixture.funcionario.codigo = '999'
        self.adicionar('Contratado após fechamento')
        self.assertEqual(self.lote(), antes)
        self.assertEqual(self.competencia.apuracao_fechada, snapshot)
        self.assertNotIn('Contratado após fechamento', antes)
        for bloco in blocos(antes):
            funcionario_id = int(re.search(r'data-funcionario-id="(\d+)"', bloco)[1])
            self.assertEqual(blocos(self.fixture.html(funcionario_id=funcionario_id).text)[0], bloco)

    def test_retrato_31_dias_e_notas_longas_sem_truncamento(self):
        self.competencia.mes = 7
        self.fixture.calendario_conferido()
        texto = ('Observação completa com detalhes da conferência. ' * 100) + 'FIM DA NOTA'
        dias = self.db.query(MarcacaoPonto).order_by(MarcacaoPonto.data).all()
        dias[0].observacoes = texto
        self.db.commit()
        individual = self.fixture.html().text
        lote = self.lote()
        self.assertEqual(individual.count('<tr class="dia">'), 31)
        self.assertIn('@page { size:A4 portrait; margin:10mm; }', individual)
        self.assertIn(texto, individual)
        self.assertEqual(blocos(individual), blocos(lote))


if __name__ == '__main__':
    unittest.main()
