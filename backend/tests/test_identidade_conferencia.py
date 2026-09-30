import json
import sys
import unittest
from datetime import date, time
from pathlib import Path
from sqlalchemy import text, inspect
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_confiabilidade_operacional as fixture_module
from app.database.models import Funcionario
from app.database.migrations import aplicar_migracoes_compativeis
from app.funcionarios.schemas import FuncionarioRead, FuncionarioUpdate
from app.funcionarios.routes import atualizar_funcionario, listar_funcionarios
from app.apuracao.service import apurar_competencia
from app.marcacoes.routes import atualizar_marcacao
from app.marcacoes.schemas import MarcacaoUpdate
from app.importadores.txt_id_tempo_maquina import parse_txt_id_tempo_maquina

class IdentidadeConferenciaTest(unittest.TestCase):
    setUp = fixture_module.ConfiabilidadeOperacionalTest.setUp
    dia = fixture_module.ConfiabilidadeOperacionalTest.dia

    def test_fallback_e_personalizacao_preservam_origem(self):
        self.f.codigo = "000894512"
        self.db.commit()
        antes = FuncionarioRead.model_validate(self.f)
        self.assertEqual(antes.nome_apresentacao, self.f.nome)
        self.assertEqual(antes.codigo_apresentacao, "000894512")
        f = atualizar_funcionario(self.f.id, FuncionarioUpdate(nome_exibicao="João Fictício", codigo_exibicao="047"), self.db)
        depois = FuncionarioRead.model_validate(f)
        self.assertEqual(depois.nome_apresentacao, "João Fictício")
        self.assertEqual(depois.codigo_apresentacao, "047")
        self.assertEqual((f.nome, f.codigo), ("Pessoa Fictícia", "000894512"))
        self.dia()
        resumo = apurar_competencia(self.db, self.c.id)["resumo"][0]
        self.assertEqual((resumo["funcionario"], resumo["codigo"]), ("João Fictício", "047"))
        atualizar_funcionario(f.id, FuncionarioUpdate(nome_exibicao="  ", codigo_exibicao=None), self.db)
        self.assertEqual(f.nome_apresentacao, "Pessoa Fictícia")

    def test_busca_quatro_identidades_sem_acentos(self):
        self.f.codigo = "000894512"
        self.f.nome_exibicao = "João Fictício"
        self.f.codigo_exibicao = "047"
        self.db.commit()
        for termo in ("joao", "047", "pessoa", "000894512"):
            with self.subTest(termo=termo):
                self.assertEqual([f.id for f in listar_funcionarios(self.f.empresa_id, self.db, termo)], [self.f.id])
        self.assertEqual(listar_funcionarios(self.f.empresa_id, self.db, "inexistente"), [])

    def test_id_exibicao_nao_vincula_relogio(self):
        self.f.codigo = "000894512"
        self.f.codigo_exibicao = "047"
        self.f.nome_exibicao = "João Fictício"
        self.db.commit()
        for codigo, esperado in (("000894512", self.f.id), ("047", None)):
            conteudo = f"ID\tNome\tTempo\n{codigo}\tOutra Pessoa Fictícia\t01/09/2026 08:00:00\n".encode()
            resultado = parse_txt_id_tempo_maquina(conteudo, arquivo_nome="ficticio.txt", mes=9, ano=2026, funcionarios=[self.f])
            self.assertEqual(resultado["registros"][0]["funcionario"]["id"], esperado)

    def test_contagem_por_funcionario_exclui_aguardando(self):
        self.dia()
        outra = Funcionario(empresa_id=self.f.empresa_id, escala_id=self.f.escala_id, nome="Outra Fictícia", data_admissao=date(2026,9,1), data_demissao=date(2026,9,1))
        self.db.add(outra); self.db.commit()
        self.dia(funcionario_id=outra.id, saida=None, batidas_originais='["08:00","12:00","13:00"]')
        r = apurar_competencia(self.db, self.c.id)
        por_id = {item["funcionario_id"]: item for item in r["resumo"]}
        self.assertEqual(por_id[self.f.id]["problemas"], 0)
        self.assertEqual(por_id[self.f.id]["aguardando_conferencia"], 1)
        self.assertEqual(por_id[outra.id]["problemas"], 1)
        dia = next(d for d in r["marcacoes"] if d["funcionario_id"] == outra.id)
        self.assertTrue(dia["bloqueante"])
        self.assertEqual(dia["problema_rotulo"], "Batida ímpar")

    def test_atribuicao_manual_preserva_brutas_audita_e_permite_desfazer(self):
        original = '["08:00","12:00","17:00"]'
        m = self.dia(entrada=None, saida_almoco=None, retorno_almoco=None, saida=None, origem="txt_id_tempo_maquina", batidas_originais=original)
        for campo, valor in (("entrada", time(8)), ("saida", time(17))):
            atualizar_marcacao(m.id, MarcacaoUpdate(**{campo:valor}), self.db)
        r = apurar_competencia(self.db, self.c.id)
        self.assertTrue(r["marcacoes"][0]["problema"])
        with self.assertRaises(HTTPException):
            atualizar_marcacao(m.id, MarcacaoUpdate(conferido=True), self.db)
        self.db.rollback()
        atualizar_marcacao(m.id, MarcacaoUpdate(saida_almoco=time(12)), self.db)
        self.assertTrue(apurar_competencia(self.db,self.c.id)["marcacoes"][0]["bloqueante"])
        atualizar_marcacao(m.id, MarcacaoUpdate(retorno_almoco=time(13)), self.db)
        self.assertFalse(apurar_competencia(self.db,self.c.id)["marcacoes"][0]["problema"])
        self.assertEqual(m.batidas_originais, original)
        self.assertEqual(m.origem, "txt_id_tempo_maquina")
        self.assertIn("retorno_almoco", m.historico[-1]["alteracoes"])
        atualizar_marcacao(m.id, MarcacaoUpdate(retorno_almoco=None), self.db)
        self.assertTrue(apurar_competencia(self.db,self.c.id)["marcacoes"][0]["problema"])
        self.assertEqual(m.batidas_originais, original)

    def test_duplicacao_de_horario_e_rejeitada(self):
        m = self.dia()
        with self.assertRaises(HTTPException):
            atualizar_marcacao(m.id, MarcacaoUpdate(saida_almoco=time(8)), self.db)
        self.db.rollback()
        self.assertEqual(m.saida_almoco, time(12))

    def test_migracao_12_aditiva_idempotente(self):
        fid = self.f.id
        self.db.close()
        with self.engine.begin() as c:
            c.exec_driver_sql("ALTER TABLE funcionarios DROP COLUMN nome_exibicao")
            c.exec_driver_sql("ALTER TABLE funcionarios DROP COLUMN codigo_exibicao")
            c.exec_driver_sql("PRAGMA user_version=11")
        aplicar_migracoes_compativeis(self.engine)
        aplicar_migracoes_compativeis(self.engine)
        with self.engine.connect() as c:
            linha = c.execute(text("SELECT id,nome,nome_exibicao,codigo_exibicao FROM funcionarios")).one()
            self.assertEqual(tuple(linha), (fid,"Pessoa Fictícia",None,None))
            self.assertEqual(c.exec_driver_sql("PRAGMA user_version").scalar_one(),12)
            self.assertEqual(c.exec_driver_sql("PRAGMA integrity_check").scalar_one(),"ok")

if __name__ == "__main__": unittest.main()
