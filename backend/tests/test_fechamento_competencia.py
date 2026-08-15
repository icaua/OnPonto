from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BACKEND_DIR = Path(__file__).resolve().parents[1]
FIXTURE_TXT = Path(__file__).resolve().parent / "fixtures" / "relogio_ficticio.txt"
FUSO_HORARIO_LOCAL = ZoneInfo("America/Sao_Paulo")


class FechamentoCompetenciaApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory(prefix="onponto-fechamento-")
        cls.addClassCleanup(cls.temp_dir.cleanup)

        raiz = Path(cls.temp_dir.name)
        banco = raiz / "fechamento.test.db"
        uploads = raiz / "uploads"
        uploads.mkdir()
        cls.uploads = uploads

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
        corpo: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        request = Request(
            self.base_url + caminho,
            data=corpo,
            headers=headers or {},
            method=metodo,
        )
        try:
            with urlopen(request, timeout=10) as resposta:
                return resposta.status, dict(resposta.headers.items()), resposta.read()
        except HTTPError as exc:
            return exc.code, dict(exc.headers.items()), exc.read()

    def json_request(
        self,
        metodo: str,
        caminho: str,
        payload: dict | None = None,
    ) -> tuple[int, object]:
        corpo = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"} if corpo is not None else {}
        status_http, _, conteudo = self.requisicao(metodo, caminho, corpo, headers)
        return status_http, json.loads(conteudo) if conteudo else None

    def multipart(
        self,
        campos: dict[str, object],
        nome: str,
        conteudo: bytes,
        content_type: str,
    ) -> tuple[bytes, str]:
        boundary = "----OnPontoTesteFechamento"
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
                f"Content-Type: {content_type}\r\n\r\n".encode(),
                conteudo,
                b"\r\n",
                f"--{boundary}--\r\n".encode(),
            ]
        )
        return b"".join(partes), f"multipart/form-data; boundary={boundary}"

    def criar_contexto(
        self,
        sufixo: str,
        codigos: tuple[str, ...] = ("F001",),
    ) -> tuple[dict, list[dict], dict]:
        status_http, empresa = self.json_request(
            "POST", "/empresas", {"nome": f"Empresa Fechamento {sufixo}"}
        )
        self.assertEqual(status_http, 201)
        funcionarios = []
        for indice, codigo in enumerate(codigos, start=1):
            status_http, funcionario = self.json_request(
                "POST",
                "/funcionarios",
                {
                    "empresa_id": empresa["id"],
                    "codigo": codigo,
                    "nome": f"Pessoa Fictícia {sufixo} {indice}",
                },
            )
            self.assertEqual(status_http, 201)
            funcionarios.append(funcionario)
        status_http, competencia = self.json_request(
            "POST",
            "/competencias",
            {"empresa_id": empresa["id"], "mes": 7, "ano": 2026},
        )
        self.assertEqual(status_http, 201)
        self.assertEqual(competencia["status"], "aberta")
        return empresa, funcionarios, competencia

    def obter_competencia(self, competencia_id: int) -> dict:
        status_http, competencia = self.json_request(
            "GET", f"/competencias/{competencia_id}"
        )
        self.assertEqual(status_http, 200)
        return competencia

    def criar_marcacao(
        self,
        competencia_id: int,
        funcionario_id: int,
        data_marcacao: str,
        *,
        conferido: bool,
    ) -> dict:
        status_http, marcacao = self.json_request(
            "POST",
            "/marcacoes",
            {
                "competencia_id": competencia_id,
                "funcionario_id": funcionario_id,
                "data": data_marcacao,
                "entrada": "08:00",
                "saida_almoco": "12:00",
                "retorno_almoco": "13:00",
                "saida": "17:00",
                "status_dia": "normal",
                "origem": "manual",
                "conferido": conferido,
            },
        )
        self.assertEqual(status_http, 201)
        return marcacao

    def analisar_txt(self, empresa_id: int, competencia_id: int) -> dict:
        corpo, content_type = self.multipart(
            {"empresa_id": empresa_id, "competencia_id": competencia_id},
            "relogio_ficticio.txt",
            FIXTURE_TXT.read_bytes(),
            "text/plain",
        )
        status_http, _, conteudo = self.requisicao(
            "POST",
            "/importadores/txt-log-relogio/analisar",
            corpo,
            {"Content-Type": content_type},
        )
        self.assertEqual(status_http, 201)
        return json.loads(conteudo)

    def test_fluxo_de_estados_e_acoes_explicitas_sem_atalhos(self) -> None:
        empresa, (funcionario,), competencia = self.criar_contexto("Estados")

        status_http, erro_create = self.json_request(
            "POST",
            "/competencias",
            {
                "empresa_id": empresa["id"],
                "mes": 8,
                "ano": 2026,
                "status": "fechada",
            },
        )
        self.assertEqual(status_http, 422)
        self.assertTrue(erro_create["detail"])

        status_http, erro_patch = self.json_request(
            "PATCH",
            f'/competencias/{competencia["id"]}',
            {"status": "fechada", "data_fechamento": "2026-07-31"},
        )
        self.assertEqual(status_http, 422)
        self.assertTrue(erro_patch["detail"])

        status_http, erro_reabrir = self.json_request(
            "POST", f'/competencias/{competencia["id"]}/reabrir'
        )
        self.assertEqual(status_http, 409)
        self.assertEqual(erro_reabrir["detail"], "A competência não está fechada.")

        marcacao = self.criar_marcacao(
            competencia["id"], funcionario["id"], "2026-07-01", conferido=False
        )
        self.assertEqual(self.obter_competencia(competencia["id"])["status"], "em_conferencia")

        status_http, _ = self.json_request(
            "PATCH", f'/marcacoes/{marcacao["id"]}', {"conferido": True}
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(self.obter_competencia(competencia["id"])["status"], "conferida")

        status_http, _ = self.json_request(
            "PATCH", f'/marcacoes/{marcacao["id"]}', {"conferido": False}
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(self.obter_competencia(competencia["id"])["status"], "em_conferencia")

        status_http, _ = self.json_request(
            "PATCH", f'/marcacoes/{marcacao["id"]}', {"conferido": True}
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(self.obter_competencia(competencia["id"])["status"], "conferida")

        status_http, fechamento = self.json_request(
            "POST",
            f'/competencias/{competencia["id"]}/fechar',
            {"confirmar_pendencias": False},
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(fechamento["status"], "fechada")
        self.assertEqual(fechamento["total_pendencias"], 0)
        self.assertFalse(fechamento["fechamento_excepcional"])
        self.assertEqual(
            fechamento["data_fechamento"],
            datetime.now(FUSO_HORARIO_LOCAL).date().isoformat(),
        )

        status_http, erro_edicao = self.json_request(
            "PATCH", f'/competencias/{competencia["id"]}', {"observacoes": "Alteração bloqueada"}
        )
        self.assertEqual(status_http, 409)
        self.assertIn("está fechada", erro_edicao["detail"])

        status_http, reaberta = self.json_request(
            "POST", f'/competencias/{competencia["id"]}/reabrir'
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(reaberta["status"], "em_conferencia")
        self.assertIsNone(reaberta["data_fechamento"])

        status_http, fechamento_reaberta = self.json_request(
            "POST", f'/competencias/{competencia["id"]}/fechar', {}
        )
        self.assertEqual(status_http, 200)
        self.assertFalse(fechamento_reaberta["fechamento_excepcional"])
        self.assertEqual(fechamento_reaberta["total_pendencias"], 0)

    def test_fechamento_com_pendencias_exige_confirmacao_explicita(self) -> None:
        _, funcionarios, competencia = self.criar_contexto(
            "Excepcional", codigos=("E001", "E002")
        )
        ids_marcacoes = [
            self.criar_marcacao(
                competencia["id"], funcionario["id"], f"2026-07-0{indice}", conferido=False
            )["id"]
            for indice, funcionario in enumerate(funcionarios, start=1)
        ]

        status_http, bloqueio = self.json_request(
            "POST", f'/competencias/{competencia["id"]}/fechar', {}
        )
        self.assertEqual(status_http, 409)
        self.assertEqual(
            bloqueio["detail"],
            {
                "codigo": "competencia_com_pendencias",
                "mensagem": "2 registros ainda precisam de conferência.",
                "total_pendencias": 2,
            },
        )
        ainda_aberta = self.obter_competencia(competencia["id"])
        self.assertEqual(ainda_aberta["status"], "em_conferencia")
        self.assertIsNone(ainda_aberta["data_fechamento"])

        status_http, fechamento = self.json_request(
            "POST",
            f'/competencias/{competencia["id"]}/fechar',
            {"confirmar_pendencias": True},
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(fechamento["status"], "fechada")
        self.assertEqual(fechamento["total_pendencias"], 2)
        self.assertTrue(fechamento["fechamento_excepcional"])
        self.assertEqual(
            fechamento["data_fechamento"],
            datetime.now(FUSO_HORARIO_LOCAL).date().isoformat(),
        )

        status_http, reaberta = self.json_request(
            "POST", f'/competencias/{competencia["id"]}/reabrir'
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(reaberta["status"], "em_conferencia")
        status_http, marcacoes = self.json_request(
            "GET", f'/marcacoes?competencia_id={competencia["id"]}'
        )
        self.assertEqual(status_http, 200)
        self.assertEqual({item["id"] for item in marcacoes}, set(ids_marcacoes))

    def test_competencia_vazia_tambem_exige_fechamento_excepcional(self) -> None:
        _, _, competencia = self.criar_contexto("Vazia")

        status_http, bloqueio = self.json_request(
            "POST", f'/competencias/{competencia["id"]}/fechar', {}
        )
        self.assertEqual(status_http, 409)
        self.assertEqual(bloqueio["detail"]["codigo"], "competencia_sem_registros")
        self.assertEqual(bloqueio["detail"]["total_pendencias"], 0)

        status_http, fechamento = self.json_request(
            "POST",
            f'/competencias/{competencia["id"]}/fechar',
            {"confirmar_pendencias": True},
        )
        self.assertEqual(status_http, 200)
        self.assertTrue(fechamento["fechamento_excepcional"])
        self.assertEqual(fechamento["total_pendencias"], 0)

        status_http, reaberta = self.json_request(
            "POST", f'/competencias/{competencia["id"]}/reabrir'
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(reaberta["status"], "aberta")
        self.assertIsNone(reaberta["data_fechamento"])

    def test_fechada_bloqueia_mutadores_e_reabertura_preserva_txt(self) -> None:
        empresa, (funcionario,), competencia = self.criar_contexto("Guards", codigos=("F001",))
        analise = self.analisar_txt(empresa["id"], competencia["id"])
        registro_valido = next(
            item
            for item in analise["preview"]
            if item["funcionario"]["id"] == funcionario["id"] and not item["fora_da_competencia"]
        )
        status_http, confirmacao = self.json_request(
            "POST",
            "/importadores/txt-log-relogio/confirmar",
            {
                "empresa_id": empresa["id"],
                "competencia_id": competencia["id"],
                "arquivo_id": analise["arquivo"]["id"],
                "registros_ids": [registro_valido["id"]],
            },
        )
        self.assertEqual(status_http, 201)
        marcacao_id = confirmacao["marcacoes_ids"][0]
        status_http, marcacao = self.json_request("GET", f"/marcacoes/{marcacao_id}")
        self.assertEqual(status_http, 200)
        batidas_originais = marcacao["batidas_originais"]

        status_http, _ = self.json_request(
            "PATCH", f"/marcacoes/{marcacao_id}", {"conferido": True}
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(self.obter_competencia(competencia["id"])["status"], "conferida")
        status_http, _ = self.json_request(
            "POST", f'/competencias/{competencia["id"]}/fechar', {}
        )
        self.assertEqual(status_http, 200)

        status_http, bloqueio_post = self.json_request(
            "POST",
            "/marcacoes",
            {
                "competencia_id": competencia["id"],
                "funcionario_id": funcionario["id"],
                "data": "2026-07-02",
                "status_dia": "falta",
                "origem": "manual",
                "conferido": True,
            },
        )
        self.assertEqual(status_http, 409)
        self.assertIn("está fechada", bloqueio_post["detail"])

        status_http, bloqueio_patch = self.json_request(
            "PATCH", f"/marcacoes/{marcacao_id}", {"saida": "17:30"}
        )
        self.assertEqual(status_http, 409)
        self.assertIn("está fechada", bloqueio_patch["detail"])

        corpo_txt, tipo_txt = self.multipart(
            {"empresa_id": empresa["id"], "competencia_id": competencia["id"]},
            "novo_relogio.txt",
            FIXTURE_TXT.read_bytes(),
            "text/plain",
        )
        status_http, _, conteudo = self.requisicao(
            "POST",
            "/importadores/txt-log-relogio/analisar",
            corpo_txt,
            {"Content-Type": tipo_txt},
        )
        self.assertEqual(status_http, 409)
        self.assertIn("está fechada", json.loads(conteudo)["detail"])

        status_http, bloqueio_confirmar = self.json_request(
            "POST",
            "/importadores/txt-log-relogio/confirmar",
            {
                "empresa_id": empresa["id"],
                "competencia_id": competencia["id"],
                "arquivo_id": analise["arquivo"]["id"],
                "registros_ids": [registro_valido["id"]],
            },
        )
        self.assertEqual(status_http, 409)
        self.assertIn("está fechada", bloqueio_confirmar["detail"])

        corpo_arquivo, tipo_arquivo = self.multipart(
            {"competencia_id": competencia["id"]},
            "documento.pdf",
            b"PDF ficticio",
            "application/pdf",
        )
        status_http, _, conteudo = self.requisicao(
            "POST", "/arquivos", corpo_arquivo, {"Content-Type": tipo_arquivo}
        )
        self.assertEqual(status_http, 409)
        self.assertIn("está fechada", json.loads(conteudo)["detail"])

        corpo_xlsx, tipo_xlsx = self.multipart(
            {
                "empresa_id": empresa["id"],
                "competencia_id": competencia["id"],
                "mes": 7,
                "ano": 2026,
            },
            "ponto.xlsx",
            b"XLSX ficticio",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        status_http, _, conteudo = self.requisicao(
            "POST",
            "/importadores/xlsx-ponto-generico",
            corpo_xlsx,
            {"Content-Type": tipo_xlsx},
        )
        self.assertEqual(status_http, 409)
        self.assertIn("está fechada", json.loads(conteudo)["detail"])

        status_http, arquivos = self.json_request(
            "GET", f'/arquivos?competencia_id={competencia["id"]}'
        )
        self.assertEqual(status_http, 200)
        self.assertEqual([item["id"] for item in arquivos], [analise["arquivo"]["id"]])
        status_download, _, original = self.requisicao(
            "GET", f'/arquivos/{analise["arquivo"]["id"]}/download'
        )
        self.assertEqual(status_download, 200)
        self.assertEqual(original, FIXTURE_TXT.read_bytes())
        status_relatorio, _, xlsx = self.requisicao(
            "GET", f'/relatorios/excel?competencia_id={competencia["id"]}'
        )
        self.assertEqual(status_relatorio, 200)
        self.assertTrue(xlsx.startswith(b"PK"))

        status_http, reaberta = self.json_request(
            "POST", f'/competencias/{competencia["id"]}/reabrir'
        )
        self.assertEqual(status_http, 200)
        self.assertEqual(reaberta["status"], "em_conferencia")
        status_http, preservada = self.json_request("GET", f"/marcacoes/{marcacao_id}")
        self.assertEqual(status_http, 200)
        self.assertEqual(preservada["id"], marcacao_id)
        self.assertEqual(preservada["batidas_originais"], batidas_originais)
        self.assertEqual(preservada["arquivo_origem_id"], analise["arquivo"]["id"])


if __name__ == "__main__":
    unittest.main()
