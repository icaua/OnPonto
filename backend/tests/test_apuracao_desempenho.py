from datetime import date, time
from pathlib import Path
import sys
import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database.models import Base, Empresa, Escala, Funcionario, Competencia, MarcacaoPonto, HistoricoVinculoEscala
from app.apuracao.service import apurar_competencia
from app.funcionarios.historico_escalas import ResolvedorEscalas


class ApuracaoDesempenhoTest(unittest.TestCase):
    def test_40_funcionarios_30_dias_sem_consultas_por_dia(self):
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            empresa = Empresa(nome="Desempenho")
            db.add(empresa)
            db.flush()
            competencia = Competencia(empresa_id=empresa.id, mes=9, ano=2026)
            db.add(competencia)
            db.flush()
            for numero in range(40):
                escala = Escala(empresa_id=empresa.id, nome=f"Escala {numero}", jornada_seg_sex_horas=8)
                db.add(escala)
                db.flush()
                funcionario = Funcionario(empresa_id=empresa.id, nome=f"Pessoa {numero:02}", escala_id=escala.id)
                db.add(funcionario)
                db.flush()
                if numero % 2:
                    db.add(HistoricoVinculoEscala(funcionario_id=funcionario.id, escala_id=escala.id, vigente_desde=date(2026, 9, 1)))
                for dia in range(1, 31):
                    db.add(MarcacaoPonto(competencia_id=competencia.id, funcionario_id=funcionario.id,
                        data=date(2026, 9, dia), entrada=time(8), saida_almoco=time(12),
                        retorno_almoco=time(13), saida=time(17), origem="manual"))
            db.commit()
        consultas = []

        @event.listens_for(engine, "before_cursor_execute")
        def contar(_conn, _cursor, statement, _parameters, _context, _executemany):
            consultas.append(statement)

        with Session(engine) as db:
            resultado = apurar_competencia(db, 1)
            self.assertEqual(len(resultado["marcacoes"]), 1200)
            self.assertEqual(len(resultado["resumo"]), 40)
            self.assertLessEqual(len(consultas), 300)
        with Session(engine) as db:
            funcionarios = db.query(Funcionario).all()
            consultas.clear()
            resolvedor = ResolvedorEscalas(db, 1)
            self.assertEqual(len(consultas), 2)
            consultas.clear()
            for funcionario in funcionarios:
                for dia in range(1, 31):
                    self.assertEqual(resolvedor.escala_no_dia(funcionario, date(2026, 9, dia)).id, funcionario.escala_id)
            self.assertEqual(consultas, [])
