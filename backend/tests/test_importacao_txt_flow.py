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
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "relogio_ficticio.txt"


class ImportacaoTxtFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = TemporaryDirectory(prefix="onponto-txt-integration-")
        cls.addClassCleanup(cls.temp_dir.cleanup)
        raiz = Path(cls.temp_dir.name)
        banco = raiz / "onponto.test.db"
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
        if hasattr(cls, "processo") and cls.processo.poll() is None:
            cls.processo.terminate()
            try:
                cls.processo.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.processo.kill()
                cls.processo.wait(timeout=5)
        if hasattr(cls, "processo") and cls.processo.stdout:
            cls.processo.stdout.close()

    def requisicao(
        self,
        metodo: str,
        caminho: str,
        corpo: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, object]:
        request = Request(self.base_url + caminho, data=corpo, headers=headers or {}, method=metodo)
        try:
            with urlopen(request, timeout=5) as resposta:
                conteudo = resposta.read()
                return resposta.status, json.loads(conteudo) if conteudo else None
        except HTTPError as exc:
            conteudo = exc.read()
            return exc.code, json.loads(conteudo) if conteudo else None

    def json_request(self, metodo: str, caminho: str, payload: dict) -> tuple[int, object]:
        return self.requisicao(
            metodo,
            caminho,
            json.dumps(payload).encode("utf-8"),
            {"Content-Type": "application/json"},
        )

    def multipart_txt(self, campos: dict[str, object], nome: str, conteudo: bytes) -> tuple[bytes, str]:
        boundary = "----OnPontoTesteTxt"
        partes: list[bytes] = []
        for chave, valor in campos.items():
            partes.extend(
                [
                    f"--{boundary}\r\n".encode(),
                    f'Content-Disposition: form-data; name="{chave}"\r\n\r\n'.encode(),
                    str(valor).encode(),
                    b"\r\n",
                ]
            )
        partes.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="arquivo"; filename="{nome}"\r\n'.encode(),
                b"Content-Type: text/plain\r\n\r\n",
                conteudo,
                b"\r\n",
                f"--{boundary}--\r\n".encode(),
            ]
        )
        return b"".join(partes), f"multipart/form-data; boundary={boundary}"

    def test_upload_analise_previa_confirmacao_e_consulta(self) -> None:
        status_http, empresa = self.json_request("POST", "/empresas", {"nome": "Empresa TXT Fictícia"})
        self.assertEqual(status_http, 201)
        status_http, escala = self.json_request(
            "POST",
            "/escalas",
            {
                "empresa_id": empresa["id"],
                "nome": "Padrão TXT",
                "modo_apuracao": "carga_horaria",
                "jornada_seg_sex_horas": 8,
                "jornada_sabado_horas": None,
                "regime_sabado": "nao_trabalha",
                "regime_domingo": "nao_trabalha",
            },
        )
        self.assertEqual(status_http, 201)
        status_http, funcionario = self.json_request(
            "POST",
            "/funcionarios",
            {
                "empresa_id": empresa["id"],
                "codigo": "F001",
                "nome": "Alice Teste",
                "escala_id": escala["id"],
            },
        )
        self.assertEqual(status_http, 201)
        status_http, competencia = self.json_request(
            "POST",
            "/competencias",
            {"empresa_id": empresa["id"], "mes": 7, "ano": 2026},
        )
        self.assertEqual(status_http, 201)

        corpo, content_type = self.multipart_txt(
            {"empresa_id": empresa["id"], "competencia_id": competencia["id"], "mes": competencia["mes"], "ano": competencia["ano"]},
            "relogio_ficticio.txt",
            FIXTURE.read_bytes(),
        )
        status_http, analise = self.requisicao(
            "POST",
            "/importadores/analisar",
            corpo,
            {"Content-Type": content_type},
        )
        self.assertEqual(status_http, 201)
        self.assertEqual(analise["tipo_detectado"], "txt_log_relogio")
        self.assertEqual(analise["total_linhas_validas"], 7)
        self.assertEqual(analise["total_batidas"], 7)
        self.assertEqual(analise["total_dias"], 3)
        self.assertEqual(analise["total_funcionarios_encontrados"], 1)
        self.assertEqual(analise["total_funcionarios_nao_cadastrados"], 1)
        self.assertEqual(analise["registros_fora_competencia"], 1)

        status_http, apuracao = self.requisicao(
            "GET", f'/apuracao?competencia_id={competencia["id"]}'
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(len(apuracao["marcacoes"]), 31)

        status_http, antes = self.requisicao(
            "GET", f'/marcacoes?competencia_id={competencia["id"]}'
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(len(antes), 31)
        self.assertTrue(all(item["origem"] == "calendario" for item in antes))

        linha_valida = next(
            item
            for item in analise["preview"]
            if item["funcionario"]["id"] == funcionario["id"] and not item["fora_da_competencia"]
        )
        self.assertTrue(linha_valida["selecionado"])
        self.assertEqual(linha_valida["batidas_originais"][0], "08:03:17")
        self.assertTrue(any(item["fora_da_competencia"] and not item["selecionado"] for item in analise["preview"]))
        self.assertTrue(
            any(not item["funcionario"]["encontrado"] and not item["selecionado"] for item in analise["preview"])
        )
        linha_sem_cadastro = next(
            item for item in analise["preview"] if not item["funcionario"]["encontrado"]
        )

        confirmacao_payload = {
            "empresa_id": empresa["id"],
            "competencia_id": competencia["id"],
            "arquivo_id": analise["arquivo"]["id"],
            "registros_ids": [linha_valida["id"], linha_sem_cadastro["id"]],
        }
        status_http, confirmacao = self.json_request(
            "POST", "/importadores/confirmar", confirmacao_payload
        )
        self.assertEqual(status_http, 201)
        self.assertEqual(confirmacao["total_importados"], 1)
        self.assertEqual(confirmacao["total_conflitos"], 1)
        self.assertEqual(confirmacao["conflitos"][0]["tipo"], "funcionario_nao_encontrado")

        status_http, marcacoes = self.requisicao(
            "GET", f'/marcacoes?competencia_id={competencia["id"]}'
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(len(marcacoes), 31)
        marcacao_importada = next(
            item for item in marcacoes if item["data"] == linha_valida["data"]
        )
        self.assertEqual(
            marcacao_importada["batidas_originais"],
            ["08:03:17", "12:02:59", "13:01:54", "17:08:23"],
        )
        self.assertEqual(marcacao_importada["arquivo_origem_id"], analise["arquivo"]["id"])
        self.assertEqual(marcacao_importada["arquivo_origem_nome"], "relogio_ficticio.txt")
        self.assertEqual(marcacao_importada["origem"], "txt_log_relogio")
        self.assertFalse(marcacao_importada["conferido"])

        status_http, atualizada = self.json_request(
            "PATCH", f'/marcacoes/{marcacao_importada["id"]}', {"saida": "17:10", "conferido": False}
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(atualizada["saida"], "17:10:00")
        self.assertEqual(atualizada["batidas_originais"], marcacao_importada["batidas_originais"])

        status_http, erro_identidade = self.json_request(
            "PATCH", f'/marcacoes/{marcacao_importada["id"]}', {"origem": "manual"}
        )
        self.assertEqual(status_http, 422)
        self.assertTrue(erro_identidade["detail"])

        status_http, repetida = self.json_request(
            "POST", "/importadores/confirmar", confirmacao_payload
        )
        self.assertEqual(status_http, 201)
        self.assertEqual(repetida["total_importados"], 0)
        self.assertEqual(repetida["total_conflitos"], 2)
        conflito_duplicado = next(
            item for item in repetida["conflitos"] if item["tipo"] == "marcacao_duplicada"
        )
        self.assertEqual(
            conflito_duplicado["mensagem"],
            "Já existe uma marcação para este funcionário nesta data.",
        )

    def test_importacao_nao_sobrescreve_placeholder_ja_decidido_por_usuario(self) -> None:
        status_http, empresa = self.json_request(
            "POST", "/empresas", {"nome": "Empresa Calendário Decidido"}
        )
        self.assertEqual(status_http, 201)
        status_http, escala = self.json_request(
            "POST",
            "/escalas",
            {
                "empresa_id": empresa["id"],
                "nome": "Segunda a sexta",
                "modo_apuracao": "carga_horaria",
                "jornada_seg_sex_horas": 8,
                "jornada_sabado_horas": None,
                "regime_sabado": "nao_trabalha",
                "regime_domingo": "nao_trabalha",
            },
        )
        self.assertEqual(status_http, 201)
        status_http, funcionario = self.json_request(
            "POST",
            "/funcionarios",
            {
                "empresa_id": empresa["id"],
                "codigo": "F777",
                "nome": "Pessoa Calendário",
                "escala_id": escala["id"],
            },
        )
        self.assertEqual(status_http, 201)
        status_http, competencia = self.json_request(
            "POST",
            "/competencias",
            {"empresa_id": empresa["id"], "mes": 8, "ano": 2026},
        )
        self.assertEqual(status_http, 201)

        status_http, _apuracao = self.requisicao(
            "GET", f'/apuracao?competencia_id={competencia["id"]}'
        )
        self.assertEqual(status_http, 200)
        status_http, calendario = self.requisicao(
            "GET", f'/marcacoes?competencia_id={competencia["id"]}'
        )
        self.assertEqual(status_http, 200)
        dia_decidido = next(item for item in calendario if item["data"] == "2026-08-03")
        status_http, dia_decidido = self.json_request(
            "PATCH",
            f'/marcacoes/{dia_decidido["id"]}',
            {
                "status_dia": "falta",
                "conferido": True,
                "observacoes": "Classificação confirmada pelo usuário.",
            },
        )
        self.assertEqual(status_http, 200)

        cabecalho = "No\tTMNo\tEnNo\tName\tGMNo\tMode\tIn/Out\tVM\tDepartment\tDateTime"
        horarios = ["08:00:01", "12:00:02", "13:00:03", "17:00:04"]
        linhas = [cabecalho]
        for indice, horario in enumerate(horarios, start=1):
            linhas.append(
                f"{indice}\t1\tF777\tPESSOA CALENDARIO\t1\t0\t1\tDedo\tDep1\t2026-08-03 {horario}"
            )
        corpo, content_type = self.multipart_txt(
            {"empresa_id": empresa["id"], "competencia_id": competencia["id"], "mes": competencia["mes"], "ano": competencia["ano"]},
            "dia_posterior.txt",
            ("\n".join(linhas) + "\n").encode("utf-8"),
        )
        status_http, analise = self.requisicao(
            "POST",
            "/importadores/analisar",
            corpo,
            {"Content-Type": content_type},
        )
        self.assertEqual(status_http, 201)
        self.assertEqual(len(analise["preview"]), 1)

        status_http, confirmacao = self.json_request(
            "POST",
            "/importadores/confirmar",
            {
                "empresa_id": empresa["id"],
                "competencia_id": competencia["id"],
                "arquivo_id": analise["arquivo"]["id"],
                "registros_ids": [analise["preview"][0]["id"]],
            },
        )
        self.assertEqual(status_http, 201)
        self.assertEqual(confirmacao["total_importados"], 0)
        self.assertEqual(confirmacao["total_conflitos"], 1)
        self.assertEqual(confirmacao["conflitos"][0]["tipo"], "marcacao_duplicada")

        status_http, preservado = self.requisicao(
            "GET", f'/marcacoes/{dia_decidido["id"]}'
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(preservado["status_dia"], "falta")
        self.assertTrue(preservado["conferido"])
        self.assertEqual(preservado["observacoes"], "Classificação confirmada pelo usuário.")
        self.assertEqual(preservado["origem"], "manual")
        self.assertEqual(preservado["batidas_originais"], [])

    def test_dois_codigos_resolvidos_no_mesmo_dia_geram_conflito_parcial(self) -> None:
        status_http, empresa = self.json_request("POST", "/empresas", {"nome": "Empresa Alias Fictícia"})
        self.assertEqual(status_http, 201)
        status_http, funcionario = self.json_request(
            "POST",
            "/funcionarios",
            {"empresa_id": empresa["id"], "codigo": "REAL", "nome": "Colaboradora Alias"},
        )
        self.assertEqual(status_http, 201)
        status_http, competencia = self.json_request(
            "POST",
            "/competencias",
            {"empresa_id": empresa["id"], "mes": 8, "ano": 2026},
        )
        self.assertEqual(status_http, 201)

        cabecalho = "No\tTMNo\tEnNo\tName\tGMNo\tMode\tIn/Out\tVM\tDepartment\tDateTime"
        horarios = ["08:00:01", "12:00:02", "13:00:03", "17:00:04"]
        linhas = [cabecalho]
        for indice, horario in enumerate(horarios, start=1):
            linhas.append(
                f"{indice}\t1\tALIAS-A\tCOLABORADORA ALIAS\t1\t0\t1\tDedo\tDep1\t2026-08-03 {horario}"
            )
        linhas.append("5\t1\tALIAS-B\tCOLABORADORA ALIAS\t1\t0\t1\tDedo\tDep1\t2026-08-03 18:00:05")
        conteudo = ("\n".join(linhas) + "\n").encode("utf-8")
        corpo, content_type = self.multipart_txt(
            {"empresa_id": empresa["id"], "competencia_id": competencia["id"], "mes": competencia["mes"], "ano": competencia["ano"]},
            "aliases_ficticios.txt",
            conteudo,
        )
        status_http, analise = self.requisicao(
            "POST",
            "/importadores/analisar",
            corpo,
            {"Content-Type": content_type},
        )
        self.assertEqual(status_http, 201)
        self.assertEqual(len(analise["preview"]), 2)
        self.assertTrue(all(item["funcionario"]["id"] == funcionario["id"] for item in analise["preview"]))

        status_http, confirmacao = self.json_request(
            "POST",
            "/importadores/confirmar",
            {
                "empresa_id": empresa["id"],
                "competencia_id": competencia["id"],
                "arquivo_id": analise["arquivo"]["id"],
                "registros_ids": [item["id"] for item in analise["preview"]],
            },
        )
        self.assertEqual(status_http, 201)
        self.assertEqual(confirmacao["total_importados"], 1)
        self.assertEqual(confirmacao["total_conflitos"], 1)
        self.assertEqual(confirmacao["conflitos"][0]["tipo"], "marcacao_duplicada")

        status_http, marcacoes = self.requisicao(
            "GET", f'/marcacoes?competencia_id={competencia["id"]}'
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(len(marcacoes), 1)

    def test_confirmacao_rejeita_data_fora_da_competencia_mesmo_se_id_for_enviado(self) -> None:
        status_http, empresa = self.json_request(
            "POST", "/empresas", {"nome": "Empresa Data Externa Fictícia"}
        )
        self.assertEqual(status_http, 201)
        status_http, _funcionario = self.json_request(
            "POST",
            "/funcionarios",
            {"empresa_id": empresa["id"], "codigo": "F001", "nome": "Alice Teste"},
        )
        self.assertEqual(status_http, 201)
        status_http, competencia = self.json_request(
            "POST",
            "/competencias",
            {"empresa_id": empresa["id"], "mes": 7, "ano": 2026},
        )
        self.assertEqual(status_http, 201)

        corpo, content_type = self.multipart_txt(
            {"empresa_id": empresa["id"], "competencia_id": competencia["id"], "mes": competencia["mes"], "ano": competencia["ano"]},
            "relogio_ficticio.txt",
            FIXTURE.read_bytes(),
        )
        status_http, analise = self.requisicao(
            "POST",
            "/importadores/analisar",
            corpo,
            {"Content-Type": content_type},
        )
        self.assertEqual(status_http, 201)
        registro_externo = next(item for item in analise["preview"] if item["fora_da_competencia"])
        self.assertFalse(registro_externo["selecionado"])

        status_http, confirmacao = self.json_request(
            "POST",
            "/importadores/confirmar",
            {
                "empresa_id": empresa["id"],
                "competencia_id": competencia["id"],
                "arquivo_id": analise["arquivo"]["id"],
                "registros_ids": [registro_externo["id"]],
            },
        )
        self.assertEqual(status_http, 201)
        self.assertEqual(confirmacao["total_importados"], 0)
        self.assertEqual(confirmacao["total_conflitos"], 1)
        self.assertEqual(confirmacao["conflitos"][0]["tipo"], "data_fora_competencia")
        self.assertEqual(
            confirmacao["conflitos"][0]["mensagem"],
            "A data do registro está fora da competência selecionada.",
        )

        status_http, marcacoes = self.requisicao(
            "GET", f'/marcacoes?competencia_id={competencia["id"]}'
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(marcacoes, [])


if __name__ == "__main__":
    unittest.main()
