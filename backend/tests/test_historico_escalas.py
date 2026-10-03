from datetime import date
from pathlib import Path
import sys
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database.models import Base, Empresa, Escala, Funcionario, HistoricoVinculoEscala
from app.funcionarios.historico_escalas import escala_no_dia, ResolvedorEscalas


class HistoricoEscalasTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        empresa = Empresa(nome="Caracterização")
        self.db.add(empresa)
        self.db.flush()
        self.a = Escala(empresa_id=empresa.id, nome="Inicial")
        self.b = Escala(empresa_id=empresa.id, nome="Atual")
        self.db.add_all([self.a, self.b])
        self.db.flush()
        self.funcionario = Funcionario(empresa_id=empresa.id, nome="Pessoa", escala=self.b)
        self.db.add(self.funcionario)
        self.db.flush()

    def vinculo(self, escala, inicio, fim=None):
        self.db.add(HistoricoVinculoEscala(funcionario_id=self.funcionario.id, escala_id=escala.id,
            vigente_desde=date(2026, 9, inicio), vigente_ate=date(2026, 9, fim) if fim else None))
        self.db.flush()

    def conferir(self, dia, esperado):
        self.assertIs(escala_no_dia(self.db, self.funcionario, date(2026, 9, dia)), esperado)
        resolvedor = ResolvedorEscalas(self.db, self.funcionario.empresa_id)
        self.assertIs(resolvedor.escala_no_dia(self.funcionario, date(2026, 9, dia)), esperado)

    def test_sem_historico_usa_escala_atual(self):
        self.conferir(1, self.b)
        self.funcionario.escala = None
        self.conferir(30, None)

    def test_um_vinculo(self):
        self.vinculo(self.a, 1)
        self.conferir(1, self.a)
        self.conferir(30, self.a)

    def test_troca_inclusiva_prevalece_inicio_mais_recente(self):
        self.vinculo(self.b, 15)
        self.vinculo(self.a, 1, 15)
        self.conferir(14, self.a)
        self.conferir(15, self.b)
        self.conferir(16, self.b)

    def test_empate_de_inicio_prevalece_id_mais_recente(self):
        self.vinculo(self.a, 15)
        self.vinculo(self.b, 15)
        self.conferir(15, self.b)
        self.conferir(30, self.b)

    def test_lacuna_nao_usa_escala_atual(self):
        self.vinculo(self.a, 1, 10)
        self.vinculo(self.b, 20)
        self.conferir(10, self.a)
        self.conferir(11, None)
        self.conferir(19, None)
        self.conferir(20, self.b)

    def test_antes_do_primeiro_usa_primeira_escala_e_menor_id(self):
        self.vinculo(self.a, 10, 15)
        self.vinculo(self.b, 10)
        self.conferir(1, self.a)
        self.conferir(9, self.a)
        self.conferir(10, self.b)

    def test_vinculo_encerrado(self):
        self.vinculo(self.a, 5, 20)
        self.conferir(20, self.a)
        self.conferir(21, None)
