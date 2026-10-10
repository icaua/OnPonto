"""Instalador em um clique: integridade, diagnóstico da .venv, reversão e verificação rápida."""
import http.server
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
import unittest
import venv
from pathlib import Path
from unittest import mock

from test_support import TemporaryDirectory

RAIZ = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("instalar_onponto", RAIZ / "setup" / "instalar_onponto.py")
inst = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = inst  # dataclasses precisa do módulo registrado
_spec.loader.exec_module(inst)


class RegistroTeste(inst.Registro):
    def __init__(self):
        super().__init__(None)
        self.linhas = []

    def __call__(self, texto="", fim="\n"):
        self.linhas.append(texto)


def projeto_minimo(raiz: Path) -> "inst.Projeto":
    for nome, conteudo in {"backend/requirements.txt": "fastapi>=0.115,<1.0\n", "backend/app/main.py": "",
                           "frontend/index.html": "", "setup/wheels/.keep": ""}.items():
        (raiz / nome).parent.mkdir(parents=True, exist_ok=True)
        (raiz / nome).write_text(conteudo, encoding="utf-8")
    return inst.Projeto(raiz)


class ManifestoTest(unittest.TestCase):
    def setUp(self):
        pasta = TemporaryDirectory(prefix="onponto-manifesto-")
        self.addCleanup(pasta.cleanup)
        self.projeto = projeto_minimo(Path(pasta.name))
        for nome, conteudo in {"pacote_um-1.0-py3-none-any.whl": b"um", "Pacote.Dois-2.0-cp312-cp312-win_amd64.whl": b"dois"}.items():
            (self.projeto.wheels / nome).write_bytes(conteudo)

    def test_gera_versoes_travadas_e_confere(self):
        self.assertEqual(inst.gerar_manifesto(self.projeto), (2, 2))
        restricoes = self.projeto.restricoes.read_text(encoding="ascii").splitlines()
        self.assertEqual([linha for linha in restricoes if not linha.startswith("#")], ["pacote-dois==2.0", "pacote-um==1.0"])
        self.assertEqual(inst.conferir_pacotes(self.projeto), [])

    def test_detecta_corrompido_faltante_e_estranho(self):
        inst.gerar_manifesto(self.projeto)
        (self.projeto.wheels / "pacote_um-1.0-py3-none-any.whl").write_bytes(b"alterado")
        (self.projeto.wheels / "Pacote.Dois-2.0-cp312-cp312-win_amd64.whl").unlink()
        (self.projeto.wheels / "intruso-9.9-py3-none-any.whl").write_bytes(b"?")
        problemas = inst.conferir_pacotes(self.projeto)
        self.assertEqual(len(problemas), 3)
        self.assertTrue(any("corrompido" in p for p in problemas))
        self.assertTrue(any(p.startswith("falta") for p in problemas))
        self.assertTrue(any("não consta" in p for p in problemas))

    def test_sem_manifesto_ou_com_duas_versoes(self):
        self.assertEqual(inst.conferir_pacotes(self.projeto), ["setup/SHA256SUMS.txt não existe"])
        (self.projeto.wheels / "pacote_um-1.1-py3-none-any.whl").write_bytes(b"outra")
        with self.assertRaises(inst.FalhaInstalacao):
            inst.gerar_manifesto(self.projeto)

    def test_manifesto_do_repositorio_confere_com_os_pacotes(self):
        projeto = inst.Projeto(RAIZ)
        self.assertEqual(inst.conferir_pacotes(projeto), [])
        travadas = [linha for linha in projeto.restricoes.read_text(encoding="ascii").splitlines() if not linha.startswith("#")]
        self.assertEqual(travadas, inst.restricoes_dos_pacotes(projeto.wheels))
        self.assertIn(inst.INSTALADOR_PYTHON, projeto.manifesto.read_text(encoding="utf-8"))

    def test_pacotes_so_servem_para_windows_64_bits_com_312(self):
        self.assertTrue(inst.pacotes_servem_para((3, 12), windows=True, maquina="AMD64", bits_64=True))
        self.assertFalse(inst.pacotes_servem_para((3, 13), windows=True, maquina="AMD64", bits_64=True))
        self.assertFalse(inst.pacotes_servem_para((3, 12), windows=False, maquina="x86_64", bits_64=True))
        self.assertFalse(inst.pacotes_servem_para((3, 12), windows=True, maquina="AMD64", bits_64=False))


class DiagnosticoVenvTest(unittest.TestCase):
    def setUp(self):
        pasta = TemporaryDirectory(prefix="onponto-venv-")
        self.addCleanup(pasta.cleanup)
        self.venv = Path(pasta.name) / ".venv"
        self.base = inst.python_base()

    def falso(self, home):
        executavel = inst.python_da_venv(self.venv)
        executavel.parent.mkdir(parents=True)
        executavel.write_bytes(b"")
        (self.venv / "pyvenv.cfg").write_text(f"home = {home}\n", encoding="utf-8")

    def test_sem_python(self):
        self.venv.mkdir()
        self.assertIn("incompleta", inst.problema_na_venv(RegistroTeste(), self.venv, self.base))

    def test_python_de_origem_sumiu(self):
        self.falso(self.venv.parent / "python-que-nao-existe")
        self.assertIn("não existe mais", inst.problema_na_venv(RegistroTeste(), self.venv, self.base))

    def test_criada_com_outro_python(self):
        self.falso(self.venv.parent)
        self.assertIn("outro Python", inst.problema_na_venv(RegistroTeste(), self.venv, self.base))

    def test_venv_real_sem_pip(self):
        venv.create(self.venv, with_pip=False)
        self.assertIn("sem o pip", inst.problema_na_venv(RegistroTeste(), self.venv, self.base))


class TrocaDeAmbienteTest(unittest.TestCase):
    """A .venv antiga só sai quando a nova passa; qualquer falha devolve a antiga."""

    def setUp(self):
        pasta = TemporaryDirectory(prefix="onponto-troca-")
        self.addCleanup(pasta.cleanup)
        self.projeto = projeto_minimo(Path(pasta.name))
        executavel = inst.python_da_venv(self.projeto.venv)
        executavel.parent.mkdir(parents=True)
        executavel.write_bytes(b"")
        (self.projeto.venv / "pyvenv.cfg").write_text("home = C:/python-apagado\n", encoding="utf-8")
        (self.projeto.venv / "antigo.txt").write_text("anterior", encoding="utf-8")

    def criar(self, _registro, _base, destino):
        executavel = inst.python_da_venv(destino)
        executavel.parent.mkdir(parents=True)
        executavel.write_bytes(b"")
        (destino / "novo.txt").write_text("novo", encoding="utf-8")

    def executar(self, falha=None):
        instalar = mock.Mock(side_effect=falha) if falha else mock.Mock(return_value="pacotes incluídos")
        with mock.patch.object(inst, "criar_venv", self.criar), \
                mock.patch.object(inst, "instalar_bibliotecas", instalar), \
                mock.patch.object(inst, "conferir_ambiente"), \
                mock.patch.object(inst, "testar_api", return_value="um banco vazio"):
            return inst.preparar_e_instalar(RegistroTeste(), self.projeto, Path(sys.executable), recriar=False)

    def sobras(self):
        return sorted(p.name for p in self.projeto.raiz.glob(".venv-*"))

    def test_falha_devolve_a_venv_anterior(self):
        for falha in (inst.FalhaInstalacao("sem rede"), KeyboardInterrupt()):
            with self.subTest(falha=type(falha).__name__):
                with self.assertRaises(type(falha)):
                    self.executar(falha)
                self.assertTrue((self.projeto.venv / "antigo.txt").exists())
                self.assertFalse((self.projeto.venv / "novo.txt").exists())
                self.assertEqual(self.sobras(), [])

    def test_sucesso_troca_e_grava_carimbo(self):
        self.assertEqual(self.executar(), ("pacotes incluídos", "um banco vazio"))
        self.assertTrue((self.projeto.venv / "novo.txt").exists())
        self.assertFalse((self.projeto.venv / "antigo.txt").exists())
        self.assertEqual(self.sobras(), [])
        carimbo = json.loads((self.projeto.venv / inst.CARIMBO).read_text(encoding="utf-8"))
        self.assertEqual(carimbo["requisitos"], inst.assinatura_requisitos(self.projeto))
        self.assertEqual(carimbo["modo"], "pacotes incluídos")


class VerificacaoRapidaTest(unittest.TestCase):
    """Checagem que o iniciar faz antes de abrir: carimbo atual e bibliotecas carregando."""

    def setUp(self):
        pasta = TemporaryDirectory(prefix="onponto-verificar-")
        self.addCleanup(pasta.cleanup)
        self.projeto = projeto_minimo(Path(pasta.name))
        self.projeto.venv.mkdir()
        prefixo = mock.patch.object(inst.sys, "prefix", str(self.projeto.venv))
        prefixo.start()
        self.addCleanup(prefixo.stop)

    def test_estados(self):
        self.assertFalse(inst.verificar(self.projeto)[0])
        inst.gravar_carimbo(self.projeto, Path(sys.executable), "teste")
        self.assertEqual(inst.verificar(self.projeto), (True, "ok"))
        with mock.patch.object(inst, "MODULOS", ("modulo_que_nao_existe_onponto",)):
            self.assertFalse(inst.verificar(self.projeto)[0])
        self.projeto.requisitos.write_text("fastapi>=0.115,<1.0\nnova-biblioteca\n", encoding="utf-8")
        pronto, motivo = inst.verificar(self.projeto)
        self.assertFalse(pronto)
        self.assertIn("mudaram", motivo)

    def test_fora_da_venv_do_projeto_nao_conta_como_pronto(self):
        inst.gravar_carimbo(self.projeto, Path(sys.executable), "teste")
        with mock.patch.object(inst.sys, "prefix", str(self.projeto.raiz)):
            self.assertFalse(inst.verificar(self.projeto)[0])


class RespostaApi(http.server.BaseHTTPRequestHandler):
    corpo = b"{}"

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.corpo)

    def log_message(self, *_):
        pass


class OnPontoAbertoTest(unittest.TestCase):
    def servidor(self, corpo):
        manipulador = type("Manipulador", (RespostaApi,), {"corpo": corpo})
        servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), manipulador)
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        self.addCleanup(servidor.server_close)
        self.addCleanup(servidor.shutdown)
        return servidor.server_address[1]

    def test_reconhece_so_a_api_do_onponto_e_ignora_proxy(self):
        porta = self.servidor(json.dumps({"nome": "On Ponto API"}).encode())
        proxy_invalido = {"HTTP_PROXY": "http://127.0.0.1:9", "http_proxy": "http://127.0.0.1:9", "NO_PROXY": "", "no_proxy": ""}
        with mock.patch.dict(os.environ, proxy_invalido):
            self.assertTrue(inst.resposta_onponto(porta))
        self.assertFalse(inst.resposta_onponto(self.servidor(b'{"nome": "Outro servico"}')))
        self.assertFalse(inst.resposta_onponto(inst.porta_livre()))


class TentativasTest(unittest.TestCase):
    def setUp(self):
        pasta = TemporaryDirectory(prefix="onponto-tentativas-")
        self.addCleanup(pasta.cleanup)
        self.projeto = projeto_minimo(Path(pasta.name))
        self.projeto.restricoes.write_text("fastapi==0.141.1\n", encoding="ascii")
        self.executavel = Path("python")

    def test_ordem_offline_depois_internet_travada_sem_faixas(self):
        tentativas = inst.tentativas_de_instalacao(self.projeto, self.executavel, usar_pacotes=True)
        self.assertEqual([d for d, _ in tentativas], ["pacotes incluídos no On Ponto, sem internet",
                                                      "internet, nas mesmas versões testadas"])
        self.assertIn("--no-index", tentativas[0][1])
        self.assertNotIn("--no-index", tentativas[1][1])
        self.assertIn("-c", tentativas[1][1])
        sem_pacotes = inst.tentativas_de_instalacao(self.projeto, self.executavel, usar_pacotes=False)
        self.assertNotIn("--no-index", sem_pacotes[0][1])

    def test_arquivo_em_uso_repete_a_mesma_forma_e_falha_explica(self):
        respostas = [subprocess.CompletedProcess([], 1, "OSError: [WinError 32] arquivo em uso"),
                     subprocess.CompletedProcess([], 0, "ok")]
        with mock.patch.object(inst, "executar", side_effect=respostas) as executar, mock.patch.object(inst.time, "sleep"):
            modo = inst.instalar_bibliotecas(RegistroTeste(), self.projeto, self.executavel, usar_pacotes=True)
        self.assertEqual(modo, "pacotes incluídos no On Ponto, sem internet")
        self.assertEqual(executar.call_count, 2)
        falhas = [subprocess.CompletedProcess([], 1, "Could not find a version")] * 3
        with mock.patch.object(inst, "executar", side_effect=falhas):
            with self.assertRaises(inst.FalhaInstalacao) as erro:
                inst.instalar_bibliotecas(RegistroTeste(), self.projeto, self.executavel, usar_pacotes=True)
        self.assertIn("internet", erro.exception.dica)


class PastaETravaTest(unittest.TestCase):
    def setUp(self):
        pasta = TemporaryDirectory(prefix="onponto-pasta-")
        self.addCleanup(pasta.cleanup)
        self.raiz = Path(pasta.name)

    def test_zip_pasta_incompleta_e_onedrive(self):
        with self.assertRaises(inst.FalhaInstalacao) as erro:
            inst.conferir_pasta(projeto_minimo(self.raiz / "Temp1_OnPonto.zip" / "OnPonto"))
        self.assertIn("ZIP", str(erro.exception))
        (self.raiz / "vazia").mkdir()
        with self.assertRaises(inst.FalhaInstalacao) as erro:
            inst.conferir_pasta(inst.Projeto(self.raiz / "vazia"))
        self.assertIn("incompleta", str(erro.exception))
        self.assertEqual(inst.conferir_pasta(projeto_minimo(self.raiz / "normal")), [])
        self.assertIn("OneDrive", inst.conferir_pasta(projeto_minimo(self.raiz / "OneDrive - Escritorio" / "OnPonto"))[0])

    def test_trava_impede_instalacao_dupla_e_expira(self):
        trava = self.raiz / "logs" / ".instalacao.lock"
        with inst.Trava(trava):
            with self.assertRaises(inst.FalhaInstalacao):
                with inst.Trava(trava):
                    pass
        self.assertFalse(trava.exists())
        trava.write_text("123", encoding="ascii")
        antigo = time.time() - 3 * 3600
        os.utime(trava, (antigo, antigo))
        with inst.Trava(trava):
            self.assertEqual(trava.read_text(encoding="ascii"), str(os.getpid()))


@unittest.skipUnless(os.name == "nt", "atalho .lnk existe só no Windows")
class AtalhoTest(unittest.TestCase):
    def test_cria_atalho_com_caracteres_dificeis_no_caminho(self):
        pasta = TemporaryDirectory(prefix="onponto-atalho-")
        self.addCleanup(pasta.cleanup)
        raiz = Path(pasta.name) / "D'Ávila & Cia (cópia)"
        projeto = projeto_minimo(raiz)
        destino = Path(pasta.name) / "Área de Trabalho"
        destino.mkdir()
        self.assertTrue(inst.criar_atalho(RegistroTeste(), projeto, destino))
        atalho = destino / "On Ponto.lnk"
        self.assertTrue(atalho.exists())
        script = f"(New-Object -ComObject WScript.Shell).CreateShortcut('{str(atalho).replace(chr(39), chr(39) * 2)}').TargetPath"
        alvo = subprocess.run(["powershell", "-NoProfile", "-Command",
                               "[Console]::OutputEncoding=[Text.Encoding]::UTF8;" + script],
                              capture_output=True, text=True, encoding="utf-8").stdout.strip()
        self.assertEqual(alvo, str(raiz / "iniciar_onponto.bat"))


if __name__ == "__main__":
    unittest.main()
