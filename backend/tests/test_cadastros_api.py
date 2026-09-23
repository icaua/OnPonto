from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from test_support import TemporaryDirectory
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BACKEND_DIR = Path(__file__).resolve().parents[1]


class CadastrosApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = TemporaryDirectory(prefix="onponto-cadastros-")
        cls.addClassCleanup(cls.temp_dir.cleanup)

        raiz = Path(cls.temp_dir.name)
        banco = raiz / "onponto-cadastros.test.db"
        uploads = raiz / "uploads"
        uploads.mkdir()

        with socket.socket() as servidor:
            servidor.bind(("127.0.0.1", 0))
            cls.porta = servidor.getsockname()[1]

        ambiente = os.environ.copy()
        ambiente["ONPONTO_DATABASE_URL"] = f"sqlite:///{banco}"
        ambiente["ONPONTO_UPLOADS_DIR"] = str(uploads)
        cls.processo = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(cls.porta),
                "--log-level",
                "warning",
            ],
            cwd=BACKEND_DIR,
            env=ambiente,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        cls.addClassCleanup(cls.encerrar_api)
        cls.base_url = f"http://127.0.0.1:{cls.porta}"

        limite = time.monotonic() + 10
        while time.monotonic() < limite:
            if cls.processo.poll() is not None:
                saida = cls.processo.stdout.read() if cls.processo.stdout else ""
                raise RuntimeError(f"A API de teste encerrou antes de iniciar:\n{saida}")
            try:
                with urlopen(cls.base_url + "/", timeout=0.5) as resposta:
                    if resposta.status == 200:
                        return
            except (URLError, TimeoutError):
                time.sleep(0.1)
        raise RuntimeError("A API de teste não iniciou dentro do tempo esperado.")

    @classmethod
    def encerrar_api(cls) -> None:
        if cls.processo.poll() is None:
            cls.processo.terminate()
            try:
                cls.processo.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.processo.kill()
                cls.processo.wait(timeout=5)

        if cls.processo.stdout:
            cls.processo.stdout.close()

    def requisicao(
        self,
        metodo: str,
        caminho: str,
        payload: dict | None = None,
    ) -> tuple[int, object]:
        corpo = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"} if corpo is not None else {}
        request = Request(self.base_url + caminho, data=corpo, headers=headers, method=metodo)
        try:
            with urlopen(request, timeout=5) as resposta:
                conteudo = resposta.read()
                return resposta.status, json.loads(conteudo) if conteudo else None
        except HTTPError as exc:
            conteudo = exc.read()
            return exc.code, json.loads(conteudo) if conteudo else None

    def criar_empresa(self, nome: str) -> dict:
        status_http, empresa = self.requisicao("POST", "/empresas", {"nome": nome})
        self.assertEqual(status_http, 201)
        self.assertIsInstance(empresa, dict)
        return empresa

    def test_auditoria_http_persistida_e_validacao_patch(self) -> None:
        empresa = self.criar_empresa("Empresa Auditoria")
        _, funcionario = self.requisicao("POST", "/funcionarios", {
            "empresa_id": empresa["id"], "nome": "Pessoa Auditoria", "codigo": "AUD-1"})
        _, competencia = self.requisicao("POST", "/competencias", {
            "empresa_id": empresa["id"], "mes": 7, "ano": 2026})
        codigo, marcacao = self.requisicao("POST", "/marcacoes", {
            "competencia_id": competencia["id"], "funcionario_id": funcionario["id"],
            "data": "2026-07-01", "entrada": "08:00", "saida_almoco": "12:00",
            "retorno_almoco": "13:00", "saida": "17:00"})
        self.assertEqual(codigo, 201)
        rota = f'/marcacoes/{marcacao["id"]}'
        codigo, _ = self.requisicao("PATCH", rota, {"retorno_almoco": "11:00"})
        self.assertEqual(codigo, 422)
        codigo, _ = self.requisicao("PATCH", rota, {"saida": "18:00"})
        self.assertEqual(codigo, 200)
        codigo, recarregada = self.requisicao("GET", rota)
        self.assertEqual(codigo, 200)
        self.assertEqual(recarregada["retorno_almoco"], "13:00:00")
        self.assertEqual(len(recarregada["historico"]), 2)
        self.assertEqual(recarregada["historico"][-1]["alteracoes"]["saida"], {
            "antes": "17:00:00", "depois": "18:00:00"})
        codigo, _ = self.requisicao("PATCH", rota, {"historico": []})
        self.assertEqual(codigo, 422)

    def test_empresa_listar_criar_e_editar(self) -> None:
        empresa = self.criar_empresa("Empresa Cadastro Fictícia")
        self.assertEqual(empresa["nome"], "Empresa Cadastro Fictícia")
        self.assertTrue(empresa["ativa"])

        status_http, empresas = self.requisicao("GET", "/empresas")
        self.assertEqual(status_http, 200)
        self.assertTrue(any(item["id"] == empresa["id"] for item in empresas))

        status_http, atualizada = self.requisicao(
            "PATCH",
            f'/empresas/{empresa["id"]}',
            {
                "nome": "Empresa Cadastro Editada",
                "cidade": "São Paulo",
                "uf": "SP",
                "ativa": False,
            },
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(atualizada["nome"], "Empresa Cadastro Editada")
        self.assertEqual((atualizada["cidade"], atualizada["uf"]), ("São Paulo", "SP"))
        self.assertFalse(atualizada["ativa"])

        status_http, aberta = self.requisicao("GET", f'/empresas/{empresa["id"]}')
        self.assertEqual(status_http, 200)
        self.assertEqual(aberta["nome"], "Empresa Cadastro Editada")

    def test_escalas_crud_validacao_e_exclusao_compativel_com_vinculo(self) -> None:
        empresa = self.criar_empresa("Empresa Escalas Fictícia")
        outra_empresa = self.criar_empresa("Outra Empresa Escalas Fictícia")
        payload = {
            "empresa_id": empresa["id"],
            "nome": "Administrativo",
            "modo_apuracao": "carga_horaria",
            "jornada_seg_sex_horas": 8,
            "jornada_sabado_horas": 4,
            "regime_sabado": "trabalha",
            "regime_domingo": "nao_trabalha",
            "tolerancia_atraso_minutos": 5,
            "tolerancia_extra_minutos": 10,
            "tolerancia_intervalo_minutos": 5,
        }
        status_http, escala = self.requisicao("POST", "/escalas", payload)
        self.assertEqual(status_http, 201)
        self.assertEqual(escala["nome"], "Administrativo")

        status_http, escalas = self.requisicao(
            "GET", f'/escalas?empresa_id={empresa["id"]}'
        )
        self.assertEqual(status_http, 200)
        self.assertEqual([item["id"] for item in escalas], [escala["id"]])

        status_http, atualizada = self.requisicao(
            "PUT",
            f'/escalas/{escala["id"]}',
            {"nome": "Administrativo atualizado", "tolerancia_atraso_minutos": 7},
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(atualizada["nome"], "Administrativo atualizado")
        self.assertEqual(atualizada["tolerancia_atraso_minutos"], 7)

        status_http, invalida = self.requisicao(
            "POST",
            "/escalas",
            {
                "empresa_id": empresa["id"],
                "nome": "Horário inválido",
                "modo_apuracao": "horario_fixo",
                "horario_entrada_prevista": "08:00",
                "horario_saida_almoco_prevista": "13:00",
                "horario_retorno_almoco_prevista": "12:00",
                "horario_saida_prevista": "17:00",
            },
        )
        self.assertEqual(status_http, 422)
        self.assertTrue(invalida["detail"])

        status_http, funcionario = self.requisicao(
            "POST",
            "/funcionarios",
            {
                "empresa_id": empresa["id"],
                "codigo": "ESC-001",
                "nome": "Pessoa com Escala",
                "escala_id": escala["id"],
            },
        )
        self.assertEqual(status_http, 201)
        self.assertEqual(funcionario["escala_id"], escala["id"])

        status_http, erro_empresa = self.requisicao(
            "POST",
            "/funcionarios",
            {
                "empresa_id": outra_empresa["id"],
                "codigo": "ESC-002",
                "nome": "Pessoa com Escala de Outra Empresa",
                "escala_id": escala["id"],
            },
        )
        self.assertEqual(status_http, 400)
        self.assertIn("não pertence", erro_empresa["detail"])

        status_http, resposta = self.requisicao(
            "DELETE", f'/escalas/{escala["id"]}'
        )
        self.assertEqual(status_http, 204)
        self.assertIsNone(resposta)
        status_http, desativada = self.requisicao("GET", f'/escalas/{escala["id"]}')
        self.assertEqual(status_http, 200)
        self.assertFalse(desativada["ativa"])

        status_http, avulsa = self.requisicao(
            "POST",
            "/escalas",
            {**payload, "nome": "Sem vínculo"},
        )
        self.assertEqual(status_http, 201)
        status_http, _ = self.requisicao("DELETE", f'/escalas/{avulsa["id"]}')
        self.assertEqual(status_http, 204)
        status_http, removida = self.requisicao("GET", f'/escalas/{avulsa["id"]}')
        self.assertEqual(status_http, 404)
        self.assertEqual(removida["detail"], "Escala não encontrada.")

    def test_funcionarios_por_empresa_edicao_status_codigo_e_duplicidade(self) -> None:
        empresa = self.criar_empresa("Empresa Funcionários Fictícia")
        outra_empresa = self.criar_empresa("Outra Empresa Funcionários Fictícia")

        status_http, funcionario = self.requisicao(
            "POST",
            "/funcionarios",
            {
                "empresa_id": empresa["id"],
                "codigo": "CAD-001",
                "nome": "Pessoa Funcionária Fictícia",
            },
        )
        self.assertEqual(status_http, 201)
        self.assertEqual(funcionario["codigo"], "CAD-001")
        self.assertTrue(funcionario["ativo"])

        status_http, funcionario_outra_empresa = self.requisicao(
            "POST",
            "/funcionarios",
            {
                "empresa_id": outra_empresa["id"],
                "codigo": "CAD-001",
                "nome": "Outra Pessoa Funcionária Fictícia",
            },
        )
        self.assertEqual(status_http, 201)

        status_http, funcionarios = self.requisicao(
            "GET", f'/funcionarios?empresa_id={empresa["id"]}'
        )
        self.assertEqual(status_http, 200)
        self.assertEqual([item["id"] for item in funcionarios], [funcionario["id"]])
        self.assertNotIn(funcionario_outra_empresa["id"], [item["id"] for item in funcionarios])

        status_http, inativado = self.requisicao(
            "PATCH",
            f'/funcionarios/{funcionario["id"]}',
            {"nome": "Pessoa Funcionária Editada", "codigo": "CAD-002", "ativo": False},
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(inativado["nome"], "Pessoa Funcionária Editada")
        self.assertEqual(inativado["codigo"], "CAD-002")
        self.assertFalse(inativado["ativo"])

        status_http, reativado = self.requisicao(
            "PATCH", f'/funcionarios/{funcionario["id"]}', {"ativo": True}
        )
        self.assertEqual(status_http, 200)
        self.assertTrue(reativado["ativo"])

        status_http, duplicado = self.requisicao(
            "POST",
            "/funcionarios",
            {
                "empresa_id": empresa["id"],
                "codigo": "CAD-002",
                "nome": "Pessoa com Código Repetido",
            },
        )
        self.assertEqual(status_http, 400)
        self.assertEqual(duplicado["detail"], "Código já usado nesta empresa.")

        status_http, segundo = self.requisicao(
            "POST",
            "/funcionarios",
            {
                "empresa_id": empresa["id"],
                "codigo": "CAD-003",
                "nome": "Segunda Pessoa Funcionária",
            },
        )
        self.assertEqual(status_http, 201)
        status_http, conflito_edicao = self.requisicao(
            "PATCH", f'/funcionarios/{segundo["id"]}', {"codigo": "CAD-002"}
        )
        self.assertEqual(status_http, 400)
        self.assertEqual(conflito_edicao["detail"], "Código já usado nesta empresa.")

        status_http, segundo_apos_conflito = self.requisicao(
            "GET", f'/funcionarios/{segundo["id"]}'
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(segundo_apos_conflito["codigo"], "CAD-003")

    def test_competencia_listar_por_empresa_criar_abrir_e_rejeitar_duplicidade(self) -> None:
        empresa = self.criar_empresa("Empresa Competência Fictícia")
        outra_empresa = self.criar_empresa("Outra Empresa Competência Fictícia")

        status_http, competencia = self.requisicao(
            "POST",
            "/competencias",
            {"empresa_id": empresa["id"], "mes": 7, "ano": 2026},
        )
        self.assertEqual(status_http, 201)
        self.assertEqual(competencia["status"], "aberta")

        status_http, competencia_outra_empresa = self.requisicao(
            "POST",
            "/competencias",
            {"empresa_id": outra_empresa["id"], "mes": 7, "ano": 2026},
        )
        self.assertEqual(status_http, 201)

        status_http, competencias = self.requisicao(
            "GET", f'/competencias?empresa_id={empresa["id"]}'
        )
        self.assertEqual(status_http, 200)
        self.assertEqual([item["id"] for item in competencias], [competencia["id"]])
        self.assertNotIn(competencia_outra_empresa["id"], [item["id"] for item in competencias])

        status_http, aberta = self.requisicao("GET", f'/competencias/{competencia["id"]}')
        self.assertEqual(status_http, 200)
        self.assertEqual(aberta["id"], competencia["id"])
        self.assertEqual((aberta["mes"], aberta["ano"]), (7, 2026))

        status_http, duplicada = self.requisicao(
            "POST",
            "/competencias",
            {"empresa_id": empresa["id"], "mes": 7, "ano": 2026},
        )
        self.assertEqual(status_http, 400)
        self.assertEqual(duplicada["detail"], "Competência já cadastrada para esta empresa.")

    def test_competencia_materializada_bloqueia_periodo_e_rejeita_data_externa(self) -> None:
        empresa = self.criar_empresa("Empresa Calendário Estrutural")
        status_http, funcionario = self.requisicao(
            "POST",
            "/funcionarios",
            {
                "empresa_id": empresa["id"],
                "codigo": "CAL-001",
                "nome": "Pessoa Calendário Estrutural",
            },
        )
        self.assertEqual(status_http, 201)
        status_http, competencia_julho = self.requisicao(
            "POST",
            "/competencias",
            {"empresa_id": empresa["id"], "mes": 7, "ano": 2026},
        )
        self.assertEqual(status_http, 201)

        status_http, apuracao = self.requisicao(
            "GET", f'/apuracao?competencia_id={competencia_julho["id"]}'
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(len(apuracao["marcacoes"]), 31)

        status_http, bloqueio = self.requisicao(
            "PATCH",
            f'/competencias/{competencia_julho["id"]}',
            {"mes": 8},
        )
        self.assertEqual(status_http, 409)
        self.assertIn("não podem ser alterados", bloqueio["detail"])

        status_http, competencia_agosto = self.requisicao(
            "POST",
            "/competencias",
            {"empresa_id": empresa["id"], "mes": 8, "ano": 2026},
        )
        self.assertEqual(status_http, 201)
        status_http, data_externa = self.requisicao(
            "POST",
            "/marcacoes",
            {
                "competencia_id": competencia_agosto["id"],
                "funcionario_id": funcionario["id"],
                "data": "2026-07-01",
                "status_dia": "normal",
                "origem": "manual",
            },
        )
        self.assertEqual(status_http, 400)
        self.assertIn("não pertence à competência", data_externa["detail"])


if __name__ == "__main__":
    unittest.main()
