import json
import sys
import unittest
from datetime import date, time
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database.session import Base
from app.database.models import Competencia, Empresa, Escala, Funcionario, MarcacaoPonto
from app.apuracao.service import apurar_competencia, calcular_trabalhado
from app.competencias.routes import fechar_competencia, reabrir_competencia
from app.competencias.schemas import FechamentoCompetenciaRequest
from app.competencias.preservacao import preservar_fechamentos_legados
from app.marcacoes.routes import atualizar_marcacao, salvar_marcacao
from app.marcacoes.schemas import MarcacaoCreate, MarcacaoUpdate, MarcacaoRead


class IntegridadeCorrecaoTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        empresa = Empresa(nome="Empresa fictícia")
        self.db.add(empresa)
        self.db.flush()
        self.escala = Escala(empresa_id=empresa.id, nome="Padrão", jornada_seg_sex_horas=8)
        self.db.add(self.escala)
        self.db.flush()
        self.funcionario = Funcionario(empresa_id=empresa.id, nome="Pessoa fictícia", escala_id=self.escala.id)
        self.competencia = Competencia(empresa_id=empresa.id, mes=7, ano=2026)
        self.db.add_all([self.funcionario, self.competencia])
        self.db.flush()
        self.marcacao = MarcacaoPonto(competencia_id=self.competencia.id, funcionario_id=self.funcionario.id,
            data=date(2026, 7, 1), entrada=time(8), saida_almoco=time(12), retorno_almoco=time(13),
            saida=time(17), conferido=True, status_dia="normal", batidas_originais='["08:00:01"]')
        self.db.add(self.marcacao)
        self.db.commit()

    def fechar(self):
        fechar_competencia(self.competencia.id, FechamentoCompetenciaRequest(confirmar_pendencias=True), self.db)

    def test_consulta_legada_fechada_nao_gera_calendario(self):
        self.competencia.status = "fechada"
        self.db.commit()
        apurar_competencia(self.db, self.competencia.id)
        self.db.commit()
        self.assertEqual(self.db.query(MarcacaoPonto).count(), 1)

    def test_fechamento_preserva_resultado_e_nao_inclui_funcionario_novo(self):
        self.fechar()
        antes = apurar_competencia(self.db, self.competencia.id)
        self.escala.jornada_seg_sex_horas = 6
        self.escala.regime_domingo = "trabalha"
        self.funcionario.nome = "Nome alterado"
        self.db.add(Funcionario(empresa_id=self.funcionario.empresa_id, nome="Nova pessoa"))
        self.db.commit()
        self.assertEqual(apurar_competencia(self.db, self.competencia.id), antes)
        self.db.commit()
        self.assertEqual(self.db.query(MarcacaoPonto).count(), 31)

    def test_reabrir_descarta_snapshot_e_novo_fechamento_recalcula(self):
        self.fechar()
        self.escala.jornada_seg_sex_horas = 6
        self.db.commit()
        reabrir_competencia(self.competencia.id, self.db)
        self.assertIsNone(self.competencia.apuracao_fechada)
        self.fechar()
        resultado = apurar_competencia(self.db, self.competencia.id)
        self.assertEqual(resultado["marcacoes"][0]["extra_minutos"], 120)

    def test_preservacao_legada_idempotente_sem_criar_dias(self):
        self.competencia.status = "fechada"
        self.db.commit()
        preservar_fechamentos_legados(self.engine)
        self.db.expire_all()
        snapshot = self.competencia.apuracao_fechada
        self.assertIn("preservacao", json.loads(snapshot))
        self.escala.jornada_seg_sex_horas = 6
        self.db.commit()
        preservar_fechamentos_legados(self.engine)
        self.db.expire_all()
        self.assertEqual(self.competencia.apuracao_fechada, snapshot)
        self.assertEqual(self.db.query(MarcacaoPonto).count(), 1)

    def test_motor_recusa_sobreposicao_e_horarios_iguais(self):
        for retorno in (time(11), time(12)):
            self.marcacao.retorno_almoco = retorno
            minutos, erro = calcular_trabalhado(self.marcacao)
            self.assertEqual(minutos, 0)
            self.assertIsNotNone(erro)

    def test_patch_parcial_invalido_nao_altera_banco_ou_historico(self):
        with self.assertRaises(HTTPException) as erro:
            atualizar_marcacao(self.marcacao.id, MarcacaoUpdate(retorno_almoco=time(11)), self.db)
        self.assertEqual(erro.exception.status_code, 422)
        self.db.rollback()
        self.assertEqual(self.marcacao.retorno_almoco, time(13))
        self.assertEqual(self.marcacao.historico, [])

    def test_auditoria_persiste_antes_depois_sem_duplicar_reenvio(self):
        marcacao_id = self.marcacao.id
        atualizar_marcacao(marcacao_id, MarcacaoUpdate(saida=time(18)), self.db)
        atualizar_marcacao(marcacao_id, MarcacaoUpdate(saida=time(18)), self.db)
        with Session(self.engine) as outra:
            registro = outra.get(MarcacaoPonto, marcacao_id)
            resposta = MarcacaoRead.model_validate(registro)
            self.assertEqual(len(resposta.historico), 1)
            self.assertEqual(resposta.historico[0]["alteracoes"]["saida"], {"antes": "17:00:00", "depois": "18:00:00"})
            self.assertEqual(resposta.batidas_originais, ["08:00:01"])

    def test_post_audita_atualizacao_e_recusa_sobreposicao(self):
        payload = dict(competencia_id=self.competencia.id, funcionario_id=self.funcionario.id,
                       data=self.marcacao.data, entrada=time(8), saida_almoco=time(12),
                       retorno_almoco=time(13), saida=time(18))
        salvar_marcacao(MarcacaoCreate(**payload), self.db)
        self.assertEqual(len(self.marcacao.historico), 1)
        payload["retorno_almoco"] = time(11)
        with self.assertRaises(HTTPException):
            salvar_marcacao(MarcacaoCreate(**payload), self.db)
        self.db.rollback()
        self.assertEqual(len(self.marcacao.historico), 1)

    def test_competencia_fechada_recusa_edicao_sem_auditar(self):
        self.fechar()
        with self.assertRaises(HTTPException) as erro:
            atualizar_marcacao(self.marcacao.id, MarcacaoUpdate(saida=time(18)), self.db)
        self.assertEqual(erro.exception.status_code, 409)
        self.assertEqual(self.marcacao.historico, [])
