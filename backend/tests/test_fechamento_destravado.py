"""Fechamento sem bloqueios artificiais: ocorrência integral, batida duplicada e gestão no relógio."""
import json
import sys
import unittest
from datetime import date, time
from pathlib import Path
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_confiabilidade_operacional as fixture_module
from test_support import TemporaryDirectory
from app.apuracao.service import apurar_competencia
from app.competencias.routes import fechar_competencia
from app.competencias.schemas import FechamentoCompetenciaRequest
from app.database.migrations import SCHEMA_VERSION, aplicar_migracoes_compativeis
from app.database.models import ArquivoRecebido, IdentificacaoIgnorada, MarcacaoPonto, OcorrenciaFuncionario
from app.importadores import routes as importadores
from app.importadores.schemas import IdentificacaoIgnoradaCreate
from app.marcacoes.routes import atualizar_marcacao, desconsiderar_batida, restaurar_batida
from app.marcacoes.schemas import DesconsideracaoBatida, MarcacaoRead, MarcacaoUpdate

JUSTIFICATIVA = "Batida duplicada no relógio."


class OcorrenciaIntegralTest(unittest.TestCase):
    setUp = fixture_module.ConfiabilidadeOperacionalTest.setUp
    dia = fixture_module.ConfiabilidadeOperacionalTest.dia

    def atestado(self):
        self.db.add(OcorrenciaFuncionario(funcionario_id=self.f.id, tipo="ATESTADO", data_inicio=date(2026, 9, 1)))
        self.db.commit()

    def test_brutas_preservadas_sem_horarios_nao_travam_ocorrencia_integral(self):
        self.atestado()
        m = self.dia(entrada=None, saida_almoco=None, retorno_almoco=None, saida=None, batidas_originais='["08:00:00","12:00:00"]')
        dia = apurar_competencia(self.db, self.c.id)["marcacoes"][0]
        self.assertFalse(dia["problema"])
        atualizar_marcacao(m.id, MarcacaoUpdate(conferido=True), self.db)
        self.assertTrue(apurar_competencia(self.db, self.c.id)["marcacoes"][0]["conferido"])
        self.assertEqual(m.batidas_originais, '["08:00:00","12:00:00"]')

    def test_horarios_em_ocorrencia_integral_continuam_exigindo_revisao(self):
        self.atestado()
        self.dia(saida_almoco=None, retorno_almoco=None, saida=time(12), batidas_originais='["08:00:00","12:00:00"]')
        dia = apurar_competencia(self.db, self.c.id)["marcacoes"][0]
        self.assertTrue(dia["problema"])
        self.assertEqual(dia["pendencia_tipo"], "ocorrencia_requer_revisao")


class DesconsiderarBatidaTest(unittest.TestCase):
    setUp = fixture_module.ConfiabilidadeOperacionalTest.setUp
    dia = fixture_module.ConfiabilidadeOperacionalTest.dia

    def duplicada(self):
        return self.dia(saida_almoco=None, retorno_almoco=None, batidas_originais='["08:00:05","08:00:50","17:00:00"]')

    def test_batida_duplicada_desconsiderada_libera_conferencia_e_preserva_origem(self):
        m = self.duplicada()
        self.assertEqual(apurar_competencia(self.db, self.c.id)["marcacoes"][0]["pendencia_tipo"], "batidas_nao_atribuidas")
        resposta = MarcacaoRead.model_validate(desconsiderar_batida(m.id, DesconsideracaoBatida(indice=1, justificativa=JUSTIFICATIVA), self.db))
        self.assertEqual(resposta.batidas_desconsideradas[0]["horario"], "08:00:50")
        self.assertEqual(resposta.batidas_originais, ["08:00:05", "08:00:50", "17:00:00"])
        self.assertEqual(m.historico[-1]["title"], "Batida desconsiderada")
        self.assertIn(JUSTIFICATIVA, m.historico[-1]["description"])
        self.assertFalse(apurar_competencia(self.db, self.c.id)["marcacoes"][0]["problema"])
        atualizar_marcacao(m.id, MarcacaoUpdate(conferido=True), self.db)
        self.assertTrue(apurar_competencia(self.db, self.c.id)["fechamento"]["pode_fechar"])

    def test_restaurar_exige_reabrir_e_volta_a_bloquear(self):
        m = self.duplicada()
        desconsiderar_batida(m.id, DesconsideracaoBatida(indice=1, justificativa=JUSTIFICATIVA), self.db)
        atualizar_marcacao(m.id, MarcacaoUpdate(conferido=True), self.db)
        with self.assertRaises(HTTPException) as erro:
            restaurar_batida(m.id, 1, self.db)
        self.assertEqual(erro.exception.status_code, 409)
        self.db.rollback()
        atualizar_marcacao(m.id, MarcacaoUpdate(conferido=False), self.db)
        restaurar_batida(m.id, 1, self.db)
        self.assertIsNone(m.batidas_desconsideradas_json)
        self.assertEqual(m.historico[-1]["title"], "Batida restaurada")
        self.assertTrue(apurar_competencia(self.db, self.c.id)["marcacoes"][0]["problema"])

    def test_nao_desconsidera_horario_em_uso_para_esconder_batida_restante(self):
        m = self.dia(saida_almoco=None, retorno_almoco=None, batidas_originais='["08:00:00","12:00:00","17:00:00"]')
        antes = m.historico_json
        with self.assertRaises(HTTPException) as erro:
            desconsiderar_batida(m.id, DesconsideracaoBatida(indice=0, justificativa=JUSTIFICATIVA), self.db)
        self.assertEqual(erro.exception.status_code, 409)
        self.db.rollback()
        self.assertIsNone(m.batidas_desconsideradas_json)
        self.assertEqual(m.historico_json, antes)
        self.assertFalse(apurar_competencia(self.db, self.c.id)["fechamento"]["pode_fechar"])
        with self.assertRaises(HTTPException):
            atualizar_marcacao(m.id, MarcacaoUpdate(conferido=True), self.db)
        # A decisão correta sobre a batida das 12h permite conferir e fechar.
        desconsiderar_batida(m.id, DesconsideracaoBatida(indice=1, justificativa=JUSTIFICATIVA), self.db)
        atualizar_marcacao(m.id, MarcacaoUpdate(conferido=True), self.db)
        fechar_competencia(self.c.id, FechamentoCompetenciaRequest(), self.db)
        self.assertEqual(self.c.status, "fechada")

    def test_decisao_inconsistente_ja_salva_bloqueia_fechamento(self):
        m = self.dia(saida_almoco=None, retorno_almoco=None, conferido=True,
                     batidas_originais='["08:00:00","12:00:00","17:00:00"]',
                     batidas_desconsideradas_json=json.dumps([{"indice": 0, "horario": "08:00:00", "justificativa": JUSTIFICATIVA}]))
        r = apurar_competencia(self.db, self.c.id)
        self.assertEqual(r["marcacoes"][0]["pendencia_tipo"], "batida_desconsiderada_em_uso")
        self.assertFalse(r["marcacoes"][0]["conferido"])
        self.assertFalse(r["fechamento"]["pode_fechar"])
        with self.assertRaises(HTTPException):
            fechar_competencia(self.c.id, FechamentoCompetenciaRequest(confirmar_pendencias=True), self.db)
        self.db.rollback()
        self.assertNotEqual(self.c.status, "fechada")
        self.assertEqual(len(m.batidas_desconsideradas), 1)

    def test_reusar_batida_desconsiderada_volta_a_bloquear(self):
        m = self.dia(saida_almoco=None, retorno_almoco=None, batidas_originais='["08:00","12:00","17:00"]')
        desconsiderar_batida(m.id, DesconsideracaoBatida(indice=1, justificativa=JUSTIFICATIVA), self.db)
        atualizar_marcacao(m.id, MarcacaoUpdate(saida_almoco=time(12), retorno_almoco=time(13)), self.db)
        self.assertTrue(apurar_competencia(self.db, self.c.id)["marcacoes"][0]["problema"])
        with self.assertRaises(HTTPException):
            atualizar_marcacao(m.id, MarcacaoUpdate(conferido=True), self.db)
        restaurar_batida(m.id, 1, self.db)
        atualizar_marcacao(m.id, MarcacaoUpdate(conferido=True), self.db)
        self.assertTrue(apurar_competencia(self.db, self.c.id)["fechamento"]["pode_fechar"])

    def test_quatro_campos_nao_escondem_quinta_batida(self):
        m = self.dia(batidas_originais='["08:00","12:00","13:00","16:00","17:00"]')
        self.assertTrue(apurar_competencia(self.db, self.c.id)["marcacoes"][0]["problema"])
        with self.assertRaises(HTTPException):
            atualizar_marcacao(m.id, MarcacaoUpdate(conferido=True), self.db)
        desconsiderar_batida(m.id, DesconsideracaoBatida(indice=3, justificativa=JUSTIFICATIVA), self.db)
        atualizar_marcacao(m.id, MarcacaoUpdate(conferido=True), self.db)
        self.assertTrue(apurar_competencia(self.db, self.c.id)["fechamento"]["pode_fechar"])

    def test_duplicatas_no_mesmo_minuto_mantem_uma_batida_disponivel(self):
        m = self.duplicada()
        desconsiderar_batida(m.id, DesconsideracaoBatida(indice=0, justificativa=JUSTIFICATIVA), self.db)
        with self.assertRaises(HTTPException) as erro:
            desconsiderar_batida(m.id, DesconsideracaoBatida(indice=1, justificativa=JUSTIFICATIVA), self.db)
        self.assertEqual(erro.exception.status_code, 409)
        self.db.rollback()
        self.assertEqual([d["indice"] for d in m.batidas_desconsideradas], [0])
        atualizar_marcacao(m.id, MarcacaoUpdate(conferido=True), self.db)

    def test_correcao_manual_de_horario_permanece_permitida(self):
        m = self.dia(batidas_originais='["08:03","12:02","13:01","17:05"]')
        atualizar_marcacao(m.id, MarcacaoUpdate(entrada=time(8, 10), conferido=True), self.db)
        self.assertTrue(apurar_competencia(self.db, self.c.id)["fechamento"]["pode_fechar"])
        self.assertIn("entrada", m.historico[-1]["alteracoes"])

    def test_validacoes(self):
        m = self.duplicada()
        for indice, status in ((3, 422), (1, None), (1, 409)):
            with self.subTest(indice=indice, status=status):
                if status is None:
                    desconsiderar_batida(m.id, DesconsideracaoBatida(indice=indice, justificativa=JUSTIFICATIVA), self.db)
                    continue
                with self.assertRaises(HTTPException) as erro:
                    desconsiderar_batida(m.id, DesconsideracaoBatida(indice=indice, justificativa=JUSTIFICATIVA), self.db)
                self.assertEqual(erro.exception.status_code, status)
                self.db.rollback()
        with self.assertRaises(ValueError):
            DesconsideracaoBatida(indice=0, justificativa="   curta  ")
        with self.assertRaises(HTTPException) as erro:
            restaurar_batida(m.id, 0, self.db)
        self.assertEqual(erro.exception.status_code, 404)
        self.db.rollback()
        self.c.status = "fechada"
        self.db.commit()
        with self.assertRaises(HTTPException) as erro:
            desconsiderar_batida(m.id, DesconsideracaoBatida(indice=0, justificativa=JUSTIFICATIVA), self.db)
        self.assertEqual(erro.exception.status_code, 409)


class GestaoNoRelogioTest(unittest.TestCase):
    setUp_base = fixture_module.ConfiabilidadeOperacionalTest.setUp

    def setUp(self):
        self.setUp_base()
        self.f.codigo = "001"
        self.f.data_demissao = None
        self.db.commit()
        pasta = TemporaryDirectory(prefix="onponto-ignorados-")
        self.addCleanup(pasta.cleanup)
        self.uploads = Path(pasta.name)
        patch = mock.patch.object(importadores, "UPLOADS_DIR", self.uploads)
        patch.start()
        self.addCleanup(patch.stop)

    def arquivo(self, linhas, nome="relogio.txt"):
        caminho = self.uploads / nome
        conteudo = "ID\tNome\tTempo\n" + "".join(f"{codigo}\t{pessoa}\t{dia:02d}/09/2026 {hora}:00\n" for codigo, pessoa, dia, hora in linhas)
        caminho.write_bytes(conteudo.encode("utf-8"))
        registro = ArquivoRecebido(competencia_id=self.c.id, nome_original=nome, caminho_arquivo=str(caminho), tipo_arquivo="txt")
        self.db.add(registro)
        self.db.commit()
        return registro

    def ignorar(self, **campos):
        dados = {"empresa_id": self.f.empresa_id, "codigo_origem": "900", "nome_origem": "Diretora Fictícia",
                 "justificativa": "Gestão não controla jornada."}
        dados.update(campos)
        return importadores.ignorar_identificacao(IdentificacaoIgnoradaCreate(**dados), self.db)

    def gestao_e_funcionario(self):
        return self.arquivo([("001", "Pessoa Fictícia", 1, "08:00"), ("001", "Pessoa Fictícia", 1, "17:00"),
                             ("900", "Diretora Fictícia", 1, "09:10"), ("900", "Diretora Fictícia", 2, "09:15")])

    def test_ignorar_pessoa_exclui_pendencias_com_trilha_e_libera_fechamento(self):
        arquivo = self.gestao_e_funcionario()
        analise = importadores.analisar_arquivo_salvo(self.db, self.c, arquivo)
        self.assertEqual(analise["total_funcionarios_nao_cadastrados"], 1)
        self.assertEqual(len(arquivo.controle_importacao["pendencias"]), 3)
        resposta = self.ignorar()
        self.assertEqual(resposta["registros_excluidos"], 2)
        controle = arquivo.controle_importacao
        self.assertEqual([p["codigo_origem"] for p in controle["pendencias"]], ["001"])
        self.assertTrue(all(d["regra_id"] == resposta["regra"]["id"] for d in controle["descartados"]))
        self.assertIn("Gestão não controla jornada.", controle["descartados"][0]["justificativa"])
        reanalise = importadores.analisar_arquivo_salvo(self.db, self.c, arquivo)
        ignorados = [item for item in reanalise["preview"] if item.get("ignorado")]
        self.assertEqual(len(ignorados), 2)
        self.assertFalse(any(item["selecionado"] for item in ignorados))
        self.assertEqual((reanalise["total_funcionarios_nao_cadastrados"], reanalise["total_pessoas_ignoradas"]), (0, 1))
        self.assertEqual(len(arquivo.controle_importacao["pendencias"]), 1)
        self.assertEqual(Path(arquivo.caminho_arquivo).read_text(encoding="utf-8").count("900"), 2)

    def fechar_com_pessoa_fora_da_apuracao(self, persistente):
        self.f.data_demissao = date(2026, 9, 1)
        self.db.commit()
        arquivo = self.gestao_e_funcionario()
        original = Path(arquivo.caminho_arquivo).read_bytes()
        analise = importadores.analisar_arquivo_salvo(self.db, self.c, arquivo)
        registro = next(item for item in analise["preview"] if item["funcionario"]["encontrado"])
        importadores.confirmar_importacao(importadores.ConfirmacaoImportacao(
            empresa_id=self.f.empresa_id, competencia_id=self.c.id, arquivo_id=arquivo.id,
            registros_ids=[registro["id"]]), self.db)
        m = self.db.query(MarcacaoPonto).one()
        atualizar_marcacao(m.id, MarcacaoUpdate(conferido=True), self.db)
        self.assertFalse(apurar_competencia(self.db, self.c.id)["fechamento"]["pode_fechar"])
        if persistente:
            self.ignorar()
        else:
            importadores.descartar_pendencias(arquivo.id, importadores.DescartePendencias(
                registros_ids=[p["registro_id"] for p in arquivo.controle_importacao["pendencias"]],
                justificativa="Pessoa fora da apuração neste arquivo."), self.db)
        self.assertTrue(apurar_competencia(self.db, self.c.id)["fechamento"]["pode_fechar"])
        fechar_competencia(self.c.id, FechamentoCompetenciaRequest(), self.db)
        self.assertEqual(self.c.status, "fechada")
        self.assertEqual(len(arquivo.controle_importacao["descartados"]), 2)
        self.assertEqual(self.db.query(MarcacaoPonto).count(), 1)
        self.assertEqual(Path(arquivo.caminho_arquivo).read_bytes(), original)

    def test_fecha_com_nao_cadastrada_ignorada(self):
        self.fechar_com_pessoa_fora_da_apuracao(persistente=True)

    def test_fecha_com_nao_cadastrada_excluida_apenas_do_arquivo(self):
        self.fechar_com_pessoa_fora_da_apuracao(persistente=False)

    def test_arquivo_novo_so_com_gestao_nao_bloqueia(self):
        self.ignorar()
        arquivo = self.arquivo([("900", "Diretora Fictícia", 3, "10:00")], nome="so_gestao.txt")
        importadores.analisar_arquivo_salvo(self.db, self.c, arquivo)
        self.assertEqual(arquivo.controle_importacao["estado"], "confirmada")
        self.assertEqual(arquivo.controle_importacao["pendencias"], [])
        operacional = apurar_competencia(self.db, self.c.id)
        self.assertEqual((operacional["operacional"]["analises_pendentes"], operacional["operacional"]["conflitos_importacao"]), (0, 0))
        self.assertEqual(self.db.query(MarcacaoPonto).count(), 0)

    def test_cadastro_prevalece_e_regra_duplicada_e_recusada(self):
        with self.assertRaises(HTTPException) as erro:
            self.ignorar(codigo_origem="001", nome_origem="Outra")
        self.assertEqual(erro.exception.status_code, 409)
        self.db.rollback()
        self.ignorar()
        with self.assertRaises(HTTPException) as erro:
            self.ignorar(nome_origem="Outro nome")
        self.assertEqual(erro.exception.status_code, 409)
        self.db.rollback()
        with self.assertRaises(ValueError):
            IdentificacaoIgnoradaCreate(empresa_id=self.f.empresa_id, codigo_origem=" ", nome_origem="", justificativa="Gestão não controla.")

    def test_sem_codigo_compara_nome_sem_acento(self):
        arquivo = self.arquivo([("", "Diretora Fictícia", 1, "09:10")], nome="sem_codigo.txt")
        self.ignorar(codigo_origem=None, nome_origem="DIRETORA  FICTICIA")
        importadores.analisar_arquivo_salvo(self.db, self.c, arquivo)
        self.assertEqual(arquivo.controle_importacao["pendencias"], [])

    def test_deixar_de_ignorar_devolve_pendencias(self):
        arquivo = self.gestao_e_funcionario()
        importadores.analisar_arquivo_salvo(self.db, self.c, arquivo)
        regra_id = self.ignorar()["regra"]["id"]
        importadores.descartar_pendencias(arquivo.id, importadores.DescartePendencias(
            registros_ids=[arquivo.controle_importacao["pendencias"][0]["registro_id"]], justificativa="Exclusão manual fictícia."), self.db)
        resposta = importadores.deixar_de_ignorar(regra_id, self.db)
        self.assertEqual(resposta["registros_restaurados"], 2)
        controle = arquivo.controle_importacao
        self.assertEqual(sorted(p["codigo_origem"] for p in controle["pendencias"]), ["900", "900"])
        self.assertEqual([d["codigo_origem"] for d in controle["descartados"]], ["001"])
        self.assertFalse(self.db.get(IdentificacaoIgnorada, regra_id).ativa)
        self.assertEqual(importadores.listar_ignorados(self.f.empresa_id, db=self.db), [])
        with self.assertRaises(HTTPException):
            importadores.deixar_de_ignorar(regra_id, self.db)

    def test_competencia_fechada_nao_e_reescrita(self):
        arquivo = self.gestao_e_funcionario()
        importadores.analisar_arquivo_salvo(self.db, self.c, arquivo)
        antes = arquivo.controle_importacao_json
        self.c.status = "fechada"
        self.db.commit()
        self.assertEqual(self.ignorar()["registros_excluidos"], 0)
        self.assertEqual(arquivo.controle_importacao_json, antes)

    def test_pendencias_agrupadas_inclusive_de_arquivo_legado(self):
        arquivo = self.gestao_e_funcionario()
        importadores.analisar_arquivo_salvo(self.db, self.c, arquivo)
        controle = arquivo.controle_importacao
        for pendencia in controle["pendencias"]:
            for campo in ("codigo_origem", "nome_origem", "funcionario_encontrado"):
                pendencia.pop(campo)
        arquivo.controle_importacao_json = json.dumps(controle)
        self.db.commit()
        grupos = importadores.pendencias_agrupadas(arquivo.id, self.db)
        self.assertEqual([(g["codigo_origem"], g["funcionario_encontrado"], len(g["registros"])) for g in grupos],
                         [("900", False, 2), ("001", True, 1)])
        self.assertEqual(arquivo.controle_importacao_json, json.dumps(controle))


class Migracao13Test(unittest.TestCase):
    setUp = fixture_module.ConfiabilidadeOperacionalTest.setUp
    dia = fixture_module.ConfiabilidadeOperacionalTest.dia

    def test_aditiva_e_idempotente(self):
        marcacao_id = self.dia(batidas_originais='["08:00"]').id
        self.db.close()
        with self.engine.begin() as c:
            c.exec_driver_sql("DROP TABLE identificacoes_ignoradas")
            c.exec_driver_sql("ALTER TABLE marcacoes_ponto DROP COLUMN batidas_desconsideradas_json")
            c.exec_driver_sql("PRAGMA user_version=12")
        aplicar_migracoes_compativeis(self.engine)
        aplicar_migracoes_compativeis(self.engine)
        with self.engine.connect() as c:
            self.assertEqual(tuple(c.execute(text("SELECT id, batidas_originais, batidas_desconsideradas_json FROM marcacoes_ponto")).one()),
                             (marcacao_id, '["08:00"]', None))
            self.assertEqual(c.execute(text("SELECT count(*) FROM identificacoes_ignoradas")).scalar_one(), 0)
            self.assertEqual(c.exec_driver_sql("PRAGMA user_version").scalar_one(), SCHEMA_VERSION)
            self.assertEqual(c.exec_driver_sql("PRAGMA integrity_check").scalar_one(), "ok")


if __name__ == "__main__":
    unittest.main()
