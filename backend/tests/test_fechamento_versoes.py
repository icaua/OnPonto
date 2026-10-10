from datetime import date
from io import BytesIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from app.database.session import Base
from app.database.models import Competencia, FechamentoVersao, ReaberturaFechamento, MarcacaoPonto, LancamentoBancoHoras, ArquivoRecebido
from app.database.migrations import aplicar_migracoes_compativeis
from app.competencias.routes import fechar_competencia, reabrir_competencia
from app.competencias.schemas import FechamentoCompetenciaRequest
from app.marcacoes.routes import atualizar_marcacao, conferir_lote, ConferenciaLote
from app.marcacoes.schemas import MarcacaoUpdate
from app.importadores import routes as importacao
from app.importadores.schemas import ConfirmacaoImportacao
from synthetic_scenarios import criar_cenario


class FechamentoVersoesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="onponto-versoes-ficticias-")
        self.addCleanup(self.temp.cleanup)
        self.engine = create_engine("sqlite:///" + str(Path(self.temp.name) / "ficticio.db"))
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.db.close)
        self.ids = criar_cenario(self.db)
        aplicar_migracoes_compativeis(self.engine)

    def fechar(self):
        return fechar_competencia(self.ids["fechavel"], FechamentoCompetenciaRequest(), self.db)

    def test_reabertura_refechamento_preservam_snapshots_ledger_e_regras(self):
        self.fechar()
        primeira = self.db.query(FechamentoVersao).one()
        snapshot = primeira.snapshot
        self.assertNotEqual(primeira.regras_json, "[]")
        reabrir_competencia(self.ids["fechavel"], self.db)
        self.assertEqual(self.db.query(FechamentoVersao).one().snapshot, snapshot)
        self.assertEqual(self.db.query(ReaberturaFechamento).one().fechamento_id, primeira.id)
        antigos = self.db.query(LancamentoBancoHoras).filter_by(versao_fechamento=1).all()
        self.assertTrue(antigos)
        self.assertTrue(all(l.estornado_em is not None for l in antigos))
        self.fechar()
        versoes = self.db.query(FechamentoVersao).order_by(FechamentoVersao.numero).all()
        self.assertEqual([v.numero for v in versoes], [1, 2])
        self.assertEqual(versoes[0].snapshot, snapshot)
        self.assertEqual(versoes[1].snapshot, self.db.get(Competencia, self.ids["fechavel"]).apuracao_fechada)

    def test_migracao_snapshot_corrente_idempotente_e_append_only(self):
        c = self.db.get(Competencia, self.ids["aberta"])
        c.status = "fechada"
        c.apuracao_fechada = '{ "legado": "bytes FICTÍCIOS" }'
        self.db.commit()
        original = c.apuracao_fechada
        aplicar_migracoes_compativeis(self.engine)
        aplicar_migracoes_compativeis(self.engine)
        self.assertEqual(self.db.query(FechamentoVersao).count(), 1)
        self.assertEqual(self.db.query(FechamentoVersao).one().snapshot, original)
        for sql in ("UPDATE fechamentos_versoes SET snapshot='{}'", "DELETE FROM fechamentos_versoes"):
            with self.assertRaises(IntegrityError): self.db.execute(text(sql))
            self.db.rollback()
        with self.engine.connect() as conexao:
            self.assertEqual(conexao.exec_driver_sql("PRAGMA foreign_key_check").all(), [])
            self.assertEqual(conexao.exec_driver_sql("PRAGMA integrity_check").scalar_one(), "ok")

    def test_falha_fechamento_reverte_snapshot_status_ledger_e_contador(self):
        with patch("app.competencias.routes.guardar_fechamento", side_effect=RuntimeError("falha FICTÍCIA")):
            with self.assertRaises(RuntimeError): self.fechar()
        c = self.db.get(Competencia, self.ids["fechavel"])
        self.assertNotEqual(c.status, "fechada")
        self.assertEqual(c.versao_fechamento, 0)
        self.assertIsNone(c.apuracao_fechada)
        self.assertEqual(self.db.query(FechamentoVersao).count(), 0)
        self.assertEqual(self.db.query(LancamentoBancoHoras).count(), 0)

    def test_fechamento_legado_sem_snapshot_nao_inventa_apuracao(self):
        c = self.db.get(Competencia, self.ids["fechavel"])
        c.status = "fechada"
        self.db.commit()
        aplicar_migracoes_compativeis(self.engine)
        registro = self.db.query(FechamentoVersao).one()
        self.assertIsNone(registro.snapshot)
        self.assertEqual(registro.origem, "fechamento_legado_sem_snapshot")
        reabrir_competencia(c.id, self.db)
        self.assertEqual(self.db.query(ReaberturaFechamento).one().fechamento_id, registro.id)

    def test_falha_reabertura_reverte_evento_e_estornos(self):
        self.fechar()
        antes = self.db.get(Competencia, self.ids["fechavel"]).apuracao_fechada
        with patch("app.competencias.routes.contar_pendencias_operacionais", side_effect=RuntimeError("falha FICTÍCIA")):
            with self.assertRaises(RuntimeError): reabrir_competencia(self.ids["fechavel"], self.db)
        self.assertEqual(self.db.get(Competencia, self.ids["fechavel"]).apuracao_fechada, antes)
        self.assertEqual(self.db.query(ReaberturaFechamento).count(), 0)
        self.assertFalse(any(l.estornado_em for l in self.db.query(LancamentoBancoHoras)))

    def test_patch_invalido_e_lote_com_falha_nao_deixam_mutacao_na_sessao(self):
        m = self.db.query(MarcacaoPonto).filter_by(competencia_id=self.ids["fechavel"]).first()
        antes = (m.entrada, m.historico_json, m.revisao)
        with self.assertRaises(HTTPException):
            atualizar_marcacao(m.id, MarcacaoUpdate(entrada="18:00", revisao=m.revisao), self.db)
        self.assertEqual((m.entrada, m.historico_json, m.revisao), antes)
        m.conferido = False
        self.db.commit()
        antes = (m.conferido, m.historico_json, m.revisao)
        with patch.object(self.db, "commit", side_effect=RuntimeError("falha FICTÍCIA")):
            with self.assertRaises(RuntimeError):
                conferir_lote(ConferenciaLote(competencia_id=m.competencia_id, marcacoes_ids=[m.id], revisoes={m.id:m.revisao}), self.db)
        self.assertEqual((m.conferido, m.historico_json, m.revisao), antes)

    def test_duas_sessoes_orm_nao_sobrescrevem_revisao(self):
        id = self.db.query(MarcacaoPonto.id).first()[0]
        with Session(self.engine) as a, Session(self.engine) as b:
            primeira, segunda = a.get(MarcacaoPonto, id), b.get(MarcacaoPonto, id)
            primeira.observacoes = "janela A"
            a.commit()
            segunda.observacoes = "janela B"
            with self.assertRaises(StaleDataError): b.commit()
            b.rollback()
            self.assertEqual(b.get(MarcacaoPonto, id).observacoes, "janela A")

    def test_falha_confirmacao_reverte_analise_e_marcacoes_preservando_original(self):
        c = self.db.get(Competencia, self.ids["aberta"])
        texto = "codigo;nome;data;hora\n" + "\n".join(
            f"F001;Pessoa FICTÍCIA 0001;2026-09-01;{h}" for h in ("08:00", "12:00", "13:00", "17:00"))
        uploads = Path(self.temp.name) / "uploads"
        with patch.object(importacao, "UPLOADS_DIR", uploads):
            previa = importacao.analisar_importacao(c.id, c.empresa_id, c.mes, c.ano,
                UploadFile(filename="ficticio.txt", file=BytesIO(texto.encode())), self.db)
            arquivo = self.db.get(ArquivoRecebido, previa["arquivo"]["id"])
            controle, observacoes = arquivo.controle_importacao_json, arquivo.observacoes
            originais = {m.id:m.batidas_originais for m in self.db.query(MarcacaoPonto)}
            payload = ConfirmacaoImportacao(empresa_id=c.empresa_id, competencia_id=c.id, arquivo_id=arquivo.id,
                registros_ids=[r["id"] for r in previa["preview"]])
            with patch.object(self.db, "commit", side_effect=SQLAlchemyError("falha FICTÍCIA")):
                with self.assertRaises(HTTPException): importacao.confirmar_importacao(payload, self.db)
            self.assertEqual((arquivo.controle_importacao_json, arquivo.observacoes), (controle, observacoes))
            self.assertEqual({m.id:m.batidas_originais for m in self.db.query(MarcacaoPonto)}, originais)
            self.assertEqual(len(list(uploads.rglob("*.txt"))), 1)
