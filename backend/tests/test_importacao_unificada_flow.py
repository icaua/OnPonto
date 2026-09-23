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
FIXTURES = BACKEND_DIR / "tests" / "fixtures"
FIXTURE_TXT_ID_TEMPO_MAQUINA = FIXTURES / "relogio_id_tempo_maquina.txt"
FIXTURE_XLSX_CARTAO_PONTO = FIXTURES / "cartao_ponto_longo_com_duplicidade.xlsx"


class ImportacaoUnificadaFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = TemporaryDirectory(prefix="onponto-importacao-unificada-")
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

    def multipart(self, campos: dict[str, object], nome: str, conteudo: bytes, content_type: str) -> tuple[bytes, str]:
        boundary = "----OnPontoTesteUnificado"
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

    def criar_empresa_e_competencia(self, sufixo: str, mes: int, ano: int) -> tuple[dict, dict]:
        status_http, empresa = self.json_request("POST", "/empresas", {"nome": f"Empresa {sufixo}"})
        self.assertEqual(status_http, 201)
        status_http, competencia = self.json_request(
            "POST", "/competencias", {"empresa_id": empresa["id"], "mes": mes, "ano": ano}
        )
        self.assertEqual(status_http, 201)
        return empresa, competencia

    def analisar(self, empresa: dict, competencia: dict, nome: str, conteudo: bytes, content_type: str) -> dict:
        corpo, tipo = self.multipart(
            {
                "empresa_id": empresa["id"],
                "competencia_id": competencia["id"],
                "mes": competencia["mes"],
                "ano": competencia["ano"],
            },
            nome,
            conteudo,
            content_type,
        )
        status_http, analise = self.requisicao("POST", "/importadores/analisar", corpo, {"Content-Type": tipo})
        self.assertEqual(status_http, 201, analise)
        return analise

    def test_txt_id_tempo_maquina_e_detectado_confirmado_e_preserva_origem(self) -> None:
        empresa, competencia = self.criar_empresa_e_competencia("TXT ID Tempo Máquina", mes=6, ano=2026)
        status_http, funcionario = self.json_request(
            "POST",
            "/funcionarios",
            {"empresa_id": empresa["id"], "codigo": "1", "nome": "Vivaldice Maria Santos de Jesus"},
        )
        self.assertEqual(status_http, 201)

        analise = self.analisar(
            empresa, competencia, "relogio_id_tempo_maquina.txt", FIXTURE_TXT_ID_TEMPO_MAQUINA.read_bytes(), "text/plain"
        )
        self.assertEqual(analise["tipo_detectado"], "txt_id_tempo_maquina")
        self.assertEqual(analise["arquivo"]["tipo_arquivo"], "txt_id_tempo_maquina")

        registro_valido = next(
            item
            for item in analise["preview"]
            if item["funcionario"]["id"] == funcionario["id"] and not item["fora_da_competencia"]
        )
        status_http, confirmacao = self.json_request(
            "POST",
            "/importadores/confirmar",
            {
                "empresa_id": empresa["id"],
                "competencia_id": competencia["id"],
                "arquivo_id": analise["arquivo"]["id"],
                "registros_ids": [registro_valido["id"]],
            },
        )
        self.assertEqual(status_http, 201)
        self.assertEqual(confirmacao["total_importados"], 1)

        status_http, marcacao = self.requisicao("GET", f'/marcacoes/{confirmacao["marcacoes_ids"][0]}')
        self.assertEqual(status_http, 200)
        self.assertEqual(marcacao["origem"], "txt_id_tempo_maquina")
        self.assertTrue(marcacao["batidas_originais"])

    def test_xlsx_cartao_ponto_e_detectado_dia_com_duplicidade_fica_pendente_e_origem_e_preservada(self) -> None:
        empresa, competencia = self.criar_empresa_e_competencia("XLSX Cartão de Ponto", mes=7, ano=2026)
        status_http, funcionario = self.json_request(
            "POST",
            "/funcionarios",
            {"empresa_id": empresa["id"], "codigo": "6009654958", "nome": "Gaby"},
        )
        self.assertEqual(status_http, 201)

        analise = self.analisar(
            empresa,
            competencia,
            "cartao_ponto_longo_com_duplicidade.xlsx",
            FIXTURE_XLSX_CARTAO_PONTO.read_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertEqual(analise["tipo_detectado"], "xlsx_cartao_ponto")

        dia_duplicidade = next(
            item
            for item in analise["preview"]
            if item["data"] == "2026-07-24" and item["funcionario"]["codigo_origem"] == "6009654958"
        )
        self.assertEqual(
            dia_duplicidade["batidas_originais"],
            ["08:02", "08:02", "11:59", "12:00", "12:59", "16:58"],
        )
        self.assertTrue(all(valor is None for valor in dia_duplicidade["interpretacao"].values()))
        self.assertIn("Mais de quatro marcações encontradas", dia_duplicidade["pendencias"])
        self.assertTrue(dia_duplicidade["selecionado"])

        dia_normal = next(
            item
            for item in analise["preview"]
            if item["data"] == "2026-07-23" and item["funcionario"]["codigo_origem"] == "6009654958"
        )
        status_http, confirmacao = self.json_request(
            "POST",
            "/importadores/confirmar",
            {
                "empresa_id": empresa["id"],
                "competencia_id": competencia["id"],
                "arquivo_id": analise["arquivo"]["id"],
                "registros_ids": [dia_duplicidade["id"], dia_normal["id"]],
            },
        )
        self.assertEqual(status_http, 201)
        self.assertEqual(confirmacao["total_importados"], 2)

        status_http, marcacoes = self.requisicao("GET", f'/marcacoes?competencia_id={competencia["id"]}')
        self.assertEqual(status_http, 200)
        marcacao_duplicidade = next(item for item in marcacoes if item["data"] == "2026-07-24")
        self.assertEqual(marcacao_duplicidade["origem"], "xlsx_cartao_ponto")
        self.assertIsNone(marcacao_duplicidade["entrada"])
        self.assertEqual(
            marcacao_duplicidade["batidas_originais"],
            ["08:02", "08:02", "11:59", "12:00", "12:59", "16:58"],
        )
        self.assertFalse(marcacao_duplicidade["conferido"])

    def test_arquivo_nao_reconhecido_por_nenhum_adaptador_retorna_400(self) -> None:
        empresa, competencia = self.criar_empresa_e_competencia("Formato Desconhecido", mes=6, ano=2026)
        corpo, tipo = self.multipart(
            {
                "empresa_id": empresa["id"],
                "competencia_id": competencia["id"],
                "mes": competencia["mes"],
                "ano": competencia["ano"],
            },
            "arquivo_estranho.txt",
            b"qualquer coisa\nsem cabecalho tabulado\n",
            "text/plain",
        )
        status_http, resposta = self.requisicao("POST", "/importadores/analisar", corpo, {"Content-Type": tipo})
        self.assertEqual(status_http, 400)
        self.assertIn("não reconhecido", resposta["detail"])


if __name__ == "__main__":
    unittest.main()
