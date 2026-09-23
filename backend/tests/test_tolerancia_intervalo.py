import sys
import unittest
from datetime import date, time
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database.models import Base, Empresa, Escala, Funcionario, MarcacaoPonto, Competencia
from app.database import migrations
from app.apuracao.service import calcular_atraso_horario_fixo, tolerancia_intervalo_efetiva
from app.escalas.schemas import EscalaCreate, EscalaUpdate, EscalaRead
from app.escalas.routes import atualizar


class ToleranciaIntervaloTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        event.listen(self.engine, 'connect', lambda c, _: c.execute('PRAGMA foreign_keys=ON'))
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose); self.addCleanup(self.db.close)
        empresa = Empresa(nome='Empresa fictícia'); self.db.add(empresa); self.db.flush()
        self.escala = Escala(empresa_id=empresa.id, nome='Fixa', modo_apuracao='horario_fixo',
            horario_entrada_prevista=time(8), horario_saida_almoco_prevista=time(12),
            horario_retorno_almoco_prevista=time(13), horario_saida_prevista=time(17),
            tolerancia_atraso_minutos=10)
        self.db.add(self.escala); self.db.flush()
        self.funcionario = Funcionario(empresa_id=empresa.id, nome='Pessoa', escala_id=self.escala.id)
        self.competencia = Competencia(empresa_id=empresa.id, mes=9, ano=2026, status='fechada', apuracao_fechada='{"preservado":true}')
        self.db.add_all([self.funcionario,self.competencia]); self.db.flush()
        self.marcacao = MarcacaoPonto(funcionario_id=self.funcionario.id, competencia_id=self.competencia.id,
            data=date(2026,9,1), entrada=time(8), saida_almoco=time(12), retorno_almoco=time(13,5), saida=time(17,5))
        self.db.add(self.marcacao); self.db.commit()

    def tornar_schema5(self):
        self.escala.tolerancia_intervalo_minutos = 0; self.db.commit(); self.db.close()
        with self.engine.begin() as c:
            c.exec_driver_sql('ALTER TABLE escalas ADD COLUMN intervalo_antigo INTEGER NOT NULL DEFAULT 0')
            c.exec_driver_sql('UPDATE escalas SET intervalo_antigo = COALESCE(tolerancia_intervalo_minutos, 0)')
            c.exec_driver_sql('ALTER TABLE escalas DROP COLUMN tolerancia_intervalo_minutos')
            c.exec_driver_sql('ALTER TABLE escalas RENAME COLUMN intervalo_antigo TO tolerancia_intervalo_minutos')
            c.exec_driver_sql('PRAGMA user_version=5')

    def test_none_herda_geral_e_zero_explicito_nao_herda(self):
        for value, effective, delay in [(None,10,0),(0,0,5),(3,3,5),(6,6,0)]:
            with self.subTest(value=value):
                self.escala.tolerancia_intervalo_minutos = value
                self.assertEqual(tolerancia_intervalo_efetiva(self.escala), effective)
                self.assertEqual(calcular_atraso_horario_fixo(self.funcionario,self.marcacao), delay)

    def test_create_read_patch_omissao_zero_e_null(self):
        dados = EscalaCreate(empresa_id=1, nome='Carga', jornada_seg_sex_horas=8)
        self.assertIsNone(dados.tolerancia_intervalo_minutos)
        self.assertIsNone(EscalaRead.model_validate(self.escala).tolerancia_intervalo_minutos)
        atualizar(self.escala.id,EscalaUpdate(tolerancia_intervalo_minutos=0),self.db)
        self.assertEqual(EscalaRead.model_validate(self.escala).tolerancia_intervalo_minutos,0)
        atualizar(self.escala.id,EscalaUpdate(nome='Renomeada'),self.db)
        self.assertEqual(self.escala.tolerancia_intervalo_minutos,0)
        atualizar(self.escala.id,EscalaUpdate(tolerancia_intervalo_minutos=None),self.db)
        self.assertIsNone(self.escala.tolerancia_intervalo_minutos)

    def test_migracao_converte_zero_preserva_positivo_snapshot_e_novo_zero(self):
        outra = Escala(empresa_id=self.escala.empresa_id,nome='Explícita',tolerancia_intervalo_minutos=7)
        self.db.add(outra);self.db.commit()
        self.tornar_schema5()
        with Session(self.engine) as db:
            self.assertEqual(calcular_atraso_horario_fixo(db.get(Funcionario,1),db.get(MarcacaoPonto,1)),5)
        result = migrations.aplicar_migracoes_compativeis(self.engine)
        self.assertEqual(result['escalas_intervalo_convertidas'],1)
        with Session(self.engine) as db:
            self.assertIsNone(db.get(Escala,1).tolerancia_intervalo_minutos)
            self.assertEqual(db.get(Escala,2).tolerancia_intervalo_minutos,7)
            self.assertEqual(calcular_atraso_horario_fixo(db.get(Funcionario,1),db.get(MarcacaoPonto,1)),0)
            self.assertEqual(db.get(Competencia,1).apuracao_fechada,'{"preservado":true}')
            db.get(Escala,1).tolerancia_intervalo_minutos=0;db.commit()
        self.assertEqual(migrations.aplicar_migracoes_compativeis(self.engine)['escalas_intervalo_convertidas'],0)
        with self.engine.connect() as c:
            self.assertEqual(c.exec_driver_sql('SELECT tolerancia_intervalo_minutos FROM escalas WHERE id=1').scalar_one(),0)
            self.assertEqual(c.exec_driver_sql('PRAGMA user_version').scalar_one(),migrations.SCHEMA_VERSION)
            self.assertEqual(c.exec_driver_sql('PRAGMA foreign_key_check').all(),[])
            self.assertEqual(c.exec_driver_sql('PRAGMA integrity_check').scalar_one(),'ok')

    def test_falha_depois_do_ddl_reverte_coluna_valor_e_versao(self):
        self.tornar_schema5()
        original = migrations._aplicar_sqlite
        def falhar(c):
            original(c)
            raise RuntimeError('Falha simulada antes do commit')
        with patch.object(migrations,'_aplicar_sqlite',side_effect=falhar), self.assertRaises(RuntimeError):
            migrations.aplicar_migracoes_compativeis(self.engine)
        with self.engine.connect() as c:
            colunas={r[1]:r for r in c.exec_driver_sql('PRAGMA table_info(escalas)')}
            self.assertEqual(colunas['tolerancia_intervalo_minutos'][3],1)
            self.assertNotIn('tolerancia_intervalo_v6',colunas)
            self.assertEqual(c.exec_driver_sql('SELECT tolerancia_intervalo_minutos FROM escalas WHERE id=1').scalar_one(),0)
            self.assertEqual(c.exec_driver_sql('PRAGMA user_version').scalar_one(),5)


if __name__ == '__main__': unittest.main()
