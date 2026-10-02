"""Instalador do On Ponto: prepara a .venv e as bibliotecas em um único passo.

Chamado por instalar_onponto.bat/.sh e, quando o ambiente precisa de reparo, pelo
iniciar_onponto.bat/.sh. Usa primeiro as bibliotecas incluídas em setup/wheels
(conferidas por SHA-256, sem internet) e só depois a internet. Uma .venv existente só
é descartada quando a nova passa em todas as verificações, e o banco real nunca é
alterado: o teste final sobe a API com uma cópia dele.

    python setup/instalar_onponto.py                  instala ou repara
    python setup/instalar_onponto.py --recriar        refaz a .venv do zero
    python setup/instalar_onponto.py --verificar      0 = pronto para iniciar, 1 = instalar
    python setup/instalar_onponto.py --gerar-manifesto   manutenção, após trocar setup/wheels
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib
import json
import os
import platform
import re
import shutil
import socket
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

WINDOWS = os.name == "nt"
PYTHON_MINIMO = (3, 10)
# setup/wheels foi gerado para CPython 3.12 em Windows 64 bits.
PYTHON_DOS_PACOTES = (3, 12)
INSTALADOR_PYTHON = "python-3.12.10-amd64.exe"
MODULOS = ("fastapi", "uvicorn", "sqlalchemy", "openpyxl", "python_multipart", "pydantic")
CARIMBO = "onponto-instalacao.json"
VERSAO_CARIMBO = 1
ESPACO_MINIMO = 400 * 1024 * 1024
LOGS_MANTIDOS = 10
# Variáveis globais que desviam o pip ou o Python da .venv do projeto.
VARIAVEIS_PERIGOSAS = ("PYTHONHOME", "PYTHONPATH", "PIP_USER", "PIP_TARGET", "PIP_PREFIX", "PIP_REQUIRE_VIRTUALENV")


class FalhaInstalacao(Exception):
    """Erro já explicado em português, com o que a pessoa pode fazer."""

    def __init__(self, mensagem: str, dica: str = "", saida: str = ""):
        super().__init__(mensagem)
        self.dica = dica
        self.saida = saida


@dataclass(frozen=True)
class Projeto:
    raiz: Path

    @property
    def setup(self) -> Path:
        return self.raiz / "setup"

    @property
    def wheels(self) -> Path:
        return self.setup / "wheels"

    @property
    def manifesto(self) -> Path:
        return self.setup / "SHA256SUMS.txt"

    @property
    def restricoes(self) -> Path:
        return self.setup / "constraints.txt"

    @property
    def requisitos(self) -> Path:
        return self.raiz / "backend" / "requirements.txt"

    @property
    def venv(self) -> Path:
        return self.raiz / ".venv"

    @property
    def logs(self) -> Path:
        return self.raiz / "logs"

    @property
    def banco(self) -> Path:
        return self.raiz / "backend" / "onponto.db"


class Registro:
    """Console resumido; o log guarda tudo, inclusive a saída do pip."""

    def __init__(self, arquivo: Path | None = None):
        self.arquivo = arquivo
        self._fp = arquivo.open("w", encoding="utf-8") if arquivo else None

    def __call__(self, texto: str = "", fim: str = "\n") -> None:
        print(texto, end=fim, flush=True)
        self._gravar(texto + fim)

    def detalhe(self, texto: str) -> None:
        self._gravar(texto.rstrip() + "\n")

    def _gravar(self, texto: str) -> None:
        if self._fp:
            self._fp.write(texto)
            self._fp.flush()

    def fechar(self) -> None:
        if self._fp:
            self._fp.close()
            self._fp = None


# ---------------------------------------------------------------- utilidades

def python_da_venv(venv: Path) -> Path:
    return venv / "Scripts" / "python.exe" if WINDOWS else venv / "bin" / "python"


def sha256(caminho: Path) -> str:
    resumo = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def mesmo_caminho(a, b) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def ambiente_limpo(**extras: str) -> dict[str, str]:
    env = {chave: valor for chave, valor in os.environ.items() if chave.upper() not in VARIAVEIS_PERIGOSAS}
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PIP_DISABLE_PIP_VERSION_CHECK="1", PIP_NO_INPUT="1")
    env.update(extras)
    return env


def executar(registro: Registro, comando, *, timeout: float, env: dict | None = None, cwd: Path | None = None):
    partes = [str(parte) for parte in comando]
    registro.detalhe("$ " + subprocess.list2cmdline(partes))
    try:
        resultado = subprocess.run(partes, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                   encoding="utf-8", errors="replace", timeout=timeout,
                                   env=env or ambiente_limpo(), cwd=cwd)
    except subprocess.TimeoutExpired as erro:
        saida = erro.stdout if isinstance(erro.stdout, str) else ""
        registro.detalhe(saida + f"\n(interrompido após {int(timeout)} s)")
        return subprocess.CompletedProcess(partes, 124, saida + "\nTempo esgotado.")
    except OSError as erro:
        registro.detalhe(f"(não executou: {erro})")
        return subprocess.CompletedProcess(partes, 127, str(erro))
    registro.detalhe(resultado.stdout)
    registro.detalhe(f"(código de saída {resultado.returncode})")
    return resultado


def apagar_pasta(pasta: Path) -> bool:
    def liberar(funcao, caminho, _erro):
        os.chmod(caminho, stat.S_IWRITE)
        funcao(caminho)

    try:
        if sys.version_info >= (3, 12):
            shutil.rmtree(pasta, onexc=liberar)
        else:
            shutil.rmtree(pasta, onerror=liberar)
    except OSError:
        return False
    return True


def ultimas_linhas(texto: str, quantidade: int = 12) -> str:
    linhas = [linha for linha in (texto or "").splitlines() if linha.strip()]
    return "\n".join(linhas[-quantidade:])


# ------------------------------------------------- pacotes incluídos (offline)

def nome_normalizado(nome: str) -> str:
    return re.sub(r"[-_.]+", "-", nome).lower()


def restricoes_dos_pacotes(wheels: Path) -> list[str]:
    """Uma versão exata por biblioteca, lida dos nomes dos arquivos .whl."""
    versoes: dict[str, str] = {}
    for arquivo in sorted(wheels.glob("*.whl")):
        nome, versao = arquivo.name.split("-")[:2]
        chave = nome_normalizado(nome)
        if versoes.setdefault(chave, versao) != versao:
            raise FalhaInstalacao(f"setup/wheels tem duas versões de {chave}: {versoes[chave]} e {versao}.",
                                  "Deixe só uma versão de cada biblioteca e gere o manifesto de novo.")
    return [f"{nome}=={versao}" for nome, versao in sorted(versoes.items())]


def gerar_manifesto(projeto: Projeto) -> tuple[int, int]:
    arquivos = sorted(projeto.wheels.glob("*.whl"))
    if not arquivos:
        raise FalhaInstalacao("Não há arquivos .whl em setup/wheels.")
    restricoes = restricoes_dos_pacotes(projeto.wheels)
    # Comentário em ASCII: o pip pode ler este arquivo com a página de código do Windows.
    projeto.restricoes.write_text(
        "# Gerado por setup/instalar_onponto.py --gerar-manifesto a partir de setup/wheels.\n"
        "# Versoes testadas juntas; a instalacao pela internet usa as mesmas.\n"
        + "\n".join(restricoes) + "\n", encoding="ascii", newline="\n")
    alvos = arquivos + [caminho for caminho in [projeto.setup / INSTALADOR_PYTHON] if caminho.exists()]
    projeto.manifesto.write_text(
        "".join(f"{sha256(caminho)}  {caminho.relative_to(projeto.setup).as_posix()}\n" for caminho in alvos),
        encoding="utf-8", newline="\n")
    return len(arquivos), len(restricoes)


def conferir_pacotes(projeto: Projeto) -> list[str]:
    """Problemas de integridade em setup/wheels; lista vazia quando tudo confere."""
    if not projeto.manifesto.exists():
        return ["setup/SHA256SUMS.txt não existe"]
    esperados: dict[str, str] = {}
    for linha in projeto.manifesto.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            resumo, nome = linha.split(maxsplit=1)
            esperados[nome.strip()] = resumo.lower()
    problemas = []
    for nome, resumo in esperados.items():
        if not nome.startswith("wheels/"):
            continue
        caminho = projeto.setup / nome
        if not caminho.exists():
            problemas.append(f"falta {nome}")
        elif sha256(caminho) != resumo:
            problemas.append(f"{nome} está corrompido")
    extras = {f"wheels/{arquivo.name}" for arquivo in projeto.wheels.glob("*.whl")} - set(esperados)
    problemas.extend(f"{nome} não consta no manifesto" for nome in sorted(extras))
    if not any(nome.startswith("wheels/") for nome in esperados):
        problemas.append("o manifesto não lista nenhum pacote")
    return problemas


def pacotes_servem_para(versao=None, windows: bool = WINDOWS, maquina: str | None = None, bits_64: bool | None = None) -> bool:
    versao = tuple((versao or sys.version_info)[:2])
    maquina = (maquina if maquina is not None else platform.machine()).lower()
    bits_64 = (sys.maxsize > 2 ** 32) if bits_64 is None else bits_64
    return windows and versao == PYTHON_DOS_PACOTES and maquina in ("amd64", "x86_64") and bits_64


# ------------------------------------------------------------------ ambiente

def python_base() -> Path:
    """Python de verdade, mesmo quando o instalador roda de dentro de uma venv."""
    if sys.prefix == sys.base_prefix:
        return Path(sys.executable)
    candidatos = [getattr(sys, "_base_executable", "")]
    if WINDOWS:
        candidatos.append(str(Path(sys.base_prefix) / "python.exe"))
    else:
        versao = f"{sys.version_info[0]}.{sys.version_info[1]}"
        candidatos += [str(Path(sys.base_prefix) / "bin" / f"python{versao}"), str(Path(sys.base_prefix) / "bin" / "python3")]
    for candidato in candidatos:
        if candidato and Path(candidato).exists() and not mesmo_caminho(Path(candidato).parent.parent, sys.prefix):
            return Path(candidato)
    raise FalhaInstalacao("Não encontrei o Python de origem.", "Execute pelo instalar_onponto.bat (ou instalar_onponto.sh).")


def ler_pyvenv(venv: Path) -> dict[str, str]:
    configuracao = venv / "pyvenv.cfg"
    if not configuracao.exists():
        return {}
    dados = {}
    for linha in configuracao.read_text(encoding="utf-8", errors="replace").splitlines():
        chave, separador, valor = linha.partition("=")
        if separador:
            dados[chave.strip().lower()] = valor.strip()
    return dados


def problema_na_venv(registro: Registro, venv: Path, base: Path) -> str | None:
    """Motivo para refazer uma .venv existente; None quando ela pode ser reaproveitada."""
    executavel = python_da_venv(venv)
    if not executavel.exists():
        return "a .venv está incompleta (sem o Python)"
    home = ler_pyvenv(venv).get("home")
    if not home or not Path(home).is_dir():
        return "o Python que criou a .venv não existe mais neste computador"
    if not mesmo_caminho(home, base.parent):
        return f"a .venv foi criada com outro Python ({home})"
    resultado = executar(registro, [executavel, "-c", "import sys, pip; print('%d.%d' % sys.version_info[:2])"], timeout=120)
    if resultado.returncode != 0:
        return "o Python da .venv não funciona ou está sem o pip"
    versao_base = f"{sys.version_info[0]}.{sys.version_info[1]}"
    if resultado.stdout.strip().splitlines()[-1:] != [versao_base]:
        return f"a .venv usa outra versão do Python (esperada {versao_base})"
    return None


def criar_venv(registro: Registro, base: Path, destino: Path) -> None:
    resultado = executar(registro, [base, "-m", "venv", destino], timeout=600)
    if resultado.returncode == 0 and python_da_venv(destino).exists():
        return
    dica = "Veja o registro da instalação para o detalhe do erro."
    if not WINDOWS and "ensurepip" in resultado.stdout:
        dica = "Instale o pacote python3-venv da sua distribuição (ex.: sudo apt install python3-venv) e execute de novo."
    raise FalhaInstalacao("Não foi possível criar o ambiente .venv.", dica, resultado.stdout)


def afastar(venv: Path) -> Path:
    """Renomeia a .venv atual para que possa voltar se a nova falhar."""
    destino = venv.with_name(f".venv-anterior-{datetime.now():%Y%m%d-%H%M%S}")
    for tentativa in range(5):
        try:
            venv.rename(destino)
            return destino
        except OSError:
            if tentativa == 4:
                break
            time.sleep(2)
    raise FalhaInstalacao("A pasta .venv está em uso e não pôde ser substituída.",
                          "Feche o On Ponto e qualquer terminal ou editor aberto nesta pasta, e execute de novo.")


def restaurar(registro: Registro, venv: Path, anterior: Path) -> None:
    if venv.exists() and not apagar_pasta(venv):
        falhou = venv.with_name(f".venv-falhou-{datetime.now():%Y%m%d-%H%M%S}")
        try:
            venv.rename(falhou)
        except OSError:
            registro(f"      ATENÇÃO: não consegui restaurar a .venv anterior; ela está em {anterior.name}.")
            return
    anterior.rename(venv)


def limpar_sobras(registro: Registro, projeto: Projeto) -> None:
    for pasta in list(projeto.raiz.glob(".venv-anterior-*")) + list(projeto.raiz.glob(".venv-falhou-*")):
        if pasta.is_dir() and not apagar_pasta(pasta):
            registro.detalhe(f"Não foi possível apagar {pasta}; tento de novo na próxima instalação.")


def assinatura_requisitos(projeto: Projeto) -> str:
    resumo = hashlib.sha256()
    for arquivo in (projeto.requisitos, projeto.restricoes):
        resumo.update(arquivo.read_bytes() if arquivo.exists() else b"")
        resumo.update(b"\0")
    return resumo.hexdigest()


def gravar_carimbo(projeto: Projeto, base: Path, modo: str) -> None:
    dados = {"versao": VERSAO_CARIMBO, "requisitos": assinatura_requisitos(projeto),
             "python": platform.python_version(), "python_base": str(base), "modo": modo,
             "instalado_em": datetime.now().isoformat(timespec="seconds")}
    (projeto.venv / CARIMBO).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def verificar(projeto: Projeto) -> tuple[bool, str]:
    """Pronto para iniciar? Roda com o Python da .venv, sem rede e sem gravar nada."""
    if not mesmo_caminho(sys.prefix, projeto.venv):
        return False, "execute a verificação com o Python da .venv"
    try:
        dados = json.loads((projeto.venv / CARIMBO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, "o ambiente ainda não foi preparado por este instalador"
    if dados.get("versao") != VERSAO_CARIMBO or dados.get("requisitos") != assinatura_requisitos(projeto):
        return False, "as dependências mudaram desde a última instalação"
    for modulo in MODULOS:
        try:
            importlib.import_module(modulo)
        except Exception as erro:  # noqa: BLE001 - qualquer falha de import exige reinstalação
            return False, f"a biblioteca {modulo} não carrega: {erro}"
    return True, "ok"


# --------------------------------------------------------------- instalação

def arquivo_em_uso(saida: str) -> bool:
    texto = saida.lower()
    return any(trecho in texto for trecho in ("winerror 5", "winerror 32", "acesso negado", "access is denied", "being used by another process"))


def tentativas_de_instalacao(projeto: Projeto, executavel: Path, usar_pacotes: bool) -> list[tuple[str, list]]:
    base = [executavel, "-m", "pip", "install", "--no-input", "-r", projeto.requisitos]
    travadas = ["-c", projeto.restricoes] if projeto.restricoes.exists() else []
    rede = ["--prefer-binary", "--timeout", "20", "--retries", "2"]
    tentativas = []
    if usar_pacotes:
        tentativas.append(("pacotes incluídos no On Ponto, sem internet",
                           base + travadas + ["--no-index", "--find-links", projeto.wheels]))
    if travadas:
        tentativas.append(("internet, nas mesmas versões testadas", base + travadas + rede))
    tentativas.append(("internet, nas versões compatíveis mais recentes", base + rede))
    return tentativas


def instalar_bibliotecas(registro: Registro, projeto: Projeto, executavel: Path, usar_pacotes: bool) -> str:
    """Instala as bibliotecas e devolve a forma que deu certo."""
    ultima = ""
    for descricao, comando in tentativas_de_instalacao(projeto, executavel, usar_pacotes):
        registro(f"      {descricao[0].upper() + descricao[1:]}... ", fim="")
        for tentativa in range(2):
            resultado = executar(registro, comando, timeout=1800)
            if resultado.returncode == 0:
                registro("ok")
                return descricao
            ultima = resultado.stdout
            if tentativa or not arquivo_em_uso(ultima):
                break
            registro.detalhe("Arquivo em uso (antivírus?); nova tentativa em 5 s.")
            time.sleep(5)
        registro("não deu certo")
    dica = "Verifique a conexão com a internet ou o proxy da empresa e execute de novo."
    if arquivo_em_uso(ultima):
        dica = "Feche o On Ponto e programas que usem a pasta .venv; o antivírus também pode segurar arquivos."
    raise FalhaInstalacao("Não foi possível instalar as bibliotecas do On Ponto.", dica, ultima)


def conferir_ambiente(registro: Registro, executavel: Path) -> None:
    resultado = executar(registro, [executavel, "-m", "pip", "check"], timeout=300)
    if resultado.returncode != 0:
        raise FalhaInstalacao("As bibliotecas instaladas são incompatíveis entre si.",
                              "Execute a instalação de novo com --recriar.", resultado.stdout)
    resultado = executar(registro, [executavel, "-c", "import " + ", ".join(MODULOS)], timeout=300)
    if resultado.returncode != 0:
        raise FalhaInstalacao("Uma biblioteca do On Ponto não pôde ser carregada.",
                              "Execute a instalação de novo com --recriar.", resultado.stdout)


def porta_livre() -> int:
    with socket.socket() as servidor:
        servidor.bind(("127.0.0.1", 0))
        return servidor.getsockname()[1]


def resposta_onponto(porta: int, timeout: float = 1.0) -> bool:
    # Sem proxy: o proxy da empresa não alcança o 127.0.0.1 desta máquina.
    abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with abridor.open(f"http://127.0.0.1:{porta}/", timeout=timeout) as resposta:
            dados = json.loads(resposta.read(4096) or b"{}")
    except Exception:  # noqa: BLE001 - porta fechada, outro serviço ou resposta inválida
        return False
    return isinstance(dados, dict) and dados.get("nome") == "On Ponto API"


def copiar_banco(origem: Path, destino: Path) -> None:
    """Cópia consistente, aberta somente para leitura, do banco real."""
    fonte = sqlite3.connect(origem.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        alvo = sqlite3.connect(destino)
        try:
            fonte.backup(alvo)
        finally:
            alvo.close()
    finally:
        fonte.close()


def testar_api(registro: Registro, projeto: Projeto, executavel: Path, limite: float = 90) -> str:
    """Sobe a API numa porta livre com uma cópia do banco; nada do real é alterado."""
    with tempfile.TemporaryDirectory(prefix="onponto-teste-", ignore_cleanup_errors=True) as pasta:
        pasta = Path(pasta)
        banco = pasta / "onponto.db"
        origem = "um banco vazio"
        if projeto.banco.exists():
            try:
                copiar_banco(projeto.banco, banco)
                origem = "uma cópia dos seus dados"
            except sqlite3.Error as erro:
                registro(f"\n      Aviso: não consegui copiar o banco para o teste ({erro}); uso um banco vazio... ", fim="")
                banco.unlink(missing_ok=True)
        porta = porta_livre()
        env = ambiente_limpo(ONPONTO_DATABASE_URL=f"sqlite:///{banco.as_posix()}", ONPONTO_UPLOADS_DIR=str(pasta / "uploads"))
        log_api = pasta / "api.log"
        with log_api.open("w", encoding="utf-8") as saida:
            processo = subprocess.Popen([str(executavel), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                                         "--port", str(porta), "--log-level", "warning"],
                                        cwd=projeto.raiz / "backend", env=env, stdout=saida, stderr=subprocess.STDOUT)
            try:
                pronto = False
                fim = time.monotonic() + limite
                while time.monotonic() < fim and processo.poll() is None:
                    if resposta_onponto(porta, timeout=2):
                        pronto = True
                        break
                    time.sleep(0.5)
            finally:
                processo.terminate()
                try:
                    processo.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    processo.kill()
                    processo.wait(timeout=15)
        texto = log_api.read_text(encoding="utf-8", errors="replace")
        registro.detalhe(f"Teste da API com {origem}:\n{texto}")
        if not pronto:
            raise FalhaInstalacao(f"O On Ponto não conseguiu iniciar no teste feito com {origem}.",
                                  "Seus dados não foram alterados. Envie o registro da instalação ao suporte.", texto)
        return origem


def criar_atalho(registro: Registro, projeto: Projeto, pasta: Path | None = None) -> bool:
    """Atalho "On Ponto" (por padrão na Área de Trabalho), apontando para iniciar_onponto.bat."""
    if not WINDOWS:
        return False

    def texto_ps(valor) -> str:
        return "'" + str(valor).replace("'", "''") + "'"

    # GetFolderPath respeita a Área de Trabalho redirecionada (ex.: para o OneDrive).
    area = texto_ps(pasta) if pasta else "[Environment]::GetFolderPath('Desktop')"
    script = ("$ErrorActionPreference='Stop';"
              f"$area={area};"
              "$atalho=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $area 'On Ponto.lnk'));"
              f"$atalho.TargetPath={texto_ps(projeto.raiz / 'iniciar_onponto.bat')};"
              f"$atalho.WorkingDirectory={texto_ps(projeto.raiz)};"
              "$atalho.Description='Abrir o On Ponto';$atalho.Save()")
    codificado = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    resultado = executar(registro, ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                    "-EncodedCommand", codificado], timeout=60)
    return resultado.returncode == 0


class Trava:
    """Impede duas instalações simultâneas na mesma pasta."""

    def __init__(self, caminho: Path, validade: float = 2 * 3600):
        self.caminho = caminho
        self.validade = validade

    def __enter__(self):
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                descritor = os.open(self.caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    recente = time.time() - self.caminho.stat().st_mtime < self.validade
                except FileNotFoundError:
                    continue
                if recente:
                    raise FalhaInstalacao("Já existe uma instalação do On Ponto em andamento nesta pasta.",
                                          f"Aguarde a outra janela terminar. Se nenhuma estiver aberta, apague {self.caminho}.")
                self.caminho.unlink(missing_ok=True)
                continue
            os.write(descritor, str(os.getpid()).encode("ascii"))
            os.close(descritor)
            return self
        raise FalhaInstalacao("Não foi possível reservar a pasta para a instalação.", f"Apague {self.caminho} e execute de novo.")

    def __exit__(self, *_):
        self.caminho.unlink(missing_ok=True)


def conferir_pasta(projeto: Projeto) -> list[str]:
    """Erros impedem a instalação; os avisos devolvidos só são mostrados."""
    if any(parte.lower().endswith(".zip") for parte in projeto.raiz.parts):
        raise FalhaInstalacao("O On Ponto está sendo executado de dentro de um arquivo ZIP.",
                              "Extraia o ZIP inteiro (botão direito > Extrair tudo) e execute a instalação na pasta extraída.")
    faltando = [nome for nome in ("backend/requirements.txt", "backend/app/main.py", "frontend/index.html")
                if not (projeto.raiz / nome).exists()]
    if faltando:
        raise FalhaInstalacao("A pasta do On Ponto está incompleta: falta " + ", ".join(faltando) + ".",
                              "Copie a pasta do On Ponto de novo, completa.")
    livre = shutil.disk_usage(projeto.raiz).free
    if livre < ESPACO_MINIMO:
        raise FalhaInstalacao(f"Pouco espaço livre no disco ({livre // (1024 * 1024)} MB).",
                              f"Libere pelo menos {ESPACO_MINIMO // (1024 * 1024)} MB e execute de novo.")
    avisos = []
    if "onedrive" in str(projeto.raiz).lower():
        avisos.append("A pasta está no OneDrive. A sincronização pode deixar o On Ponto lento;"
                      " prefira uma pasta fora dele (ex.: C:\\OnPonto).")
    return avisos


def preparar_e_instalar(registro: Registro, projeto: Projeto, base: Path, recriar: bool) -> tuple[str, str]:
    """Garante a .venv, instala e testa. Devolve (forma de instalação, origem do teste)."""
    registro("[3/6] Preparando o ambiente .venv... ", fim="")
    motivo = None
    if projeto.venv.exists():
        motivo = "pedido de recriação (--recriar)" if recriar else problema_na_venv(registro, projeto.venv, base)
    anterior = None
    if motivo:
        registro("")
        registro(f"      A .venv será refeita: {motivo}.")
        registro("      A atual só é descartada se a nova passar nos testes.")
        anterior = afastar(projeto.venv)
    try:
        if not projeto.venv.exists():
            criar_venv(registro, base, projeto.venv)
        registro("      ok" if motivo else "ok")
        executavel = python_da_venv(projeto.venv)

        registro("[4/6] Instalando as bibliotecas (pode levar alguns minutos)...")
        problemas = conferir_pacotes(projeto)
        servem = pacotes_servem_para()
        if problemas:
            registro("      Pacotes incluídos ignorados: " + "; ".join(problemas[:3]) + ".")
        elif not servem:
            registro(f"      Os pacotes incluídos são para Python {PYTHON_DOS_PACOTES[0]}.{PYTHON_DOS_PACOTES[1]} em Windows"
                     " 64 bits; as bibliotecas virão da internet.")
        modo = instalar_bibliotecas(registro, projeto, executavel, usar_pacotes=servem and not problemas)
        conferir_ambiente(registro, executavel)

        registro("[5/6] Testando o On Ponto... ", fim="")
        origem = testar_api(registro, projeto, executavel)
        registro(f"ok (com {origem})")
    except BaseException:
        if anterior is not None:
            restaurar(registro, projeto.venv, anterior)
            registro("      O ambiente anterior foi mantido.")
        raise
    if anterior is not None and not apagar_pasta(anterior):
        registro.detalhe(f"Não foi possível apagar {anterior}; será apagada na próxima instalação.")
    gravar_carimbo(projeto, base, modo)
    return modo, origem


def podar_logs(projeto: Projeto) -> None:
    antigos = sorted(projeto.logs.glob("instalacao-*.log"))[:-LOGS_MANTIDOS]
    for arquivo in antigos:
        arquivo.unlink(missing_ok=True)


def instalar(projeto: Projeto, recriar: bool = False, atalho: bool = True) -> int:
    projeto.logs.mkdir(parents=True, exist_ok=True)
    caminho_log = projeto.logs / f"instalacao-{datetime.now():%Y%m%d-%H%M%S}.log"
    registro = Registro(caminho_log)
    inicio = time.monotonic()
    registro("")
    registro("  ON PONTO - INSTALAÇÃO")
    registro("  =====================")
    registro("")
    try:
        with Trava(projeto.logs / ".instalacao.lock"):
            registro("[1/6] Conferindo a pasta do On Ponto... ", fim="")
            avisos = conferir_pasta(projeto)
            if resposta_onponto(8000):
                raise FalhaInstalacao("O On Ponto está aberto.",
                                      "Feche as janelas \"On Ponto API\" e \"On Ponto Frontend\" e execute a instalação de novo.")
            limpar_sobras(registro, projeto)
            registro("ok")
            for aviso in avisos:
                registro(f"      Aviso: {aviso}")

            base = python_base()
            registro(f"[2/6] Python {platform.python_version()} ({base})... ", fim="")
            if sys.version_info[:2] < PYTHON_MINIMO:
                raise FalhaInstalacao(f"O On Ponto precisa do Python {PYTHON_MINIMO[0]}.{PYTHON_MINIMO[1]} ou mais novo.",
                                      "Instale o Python 3.12 e execute de novo.")
            if mesmo_caminho(sys.prefix, projeto.venv):
                raise FalhaInstalacao("O instalador não pode rodar com o Python da própria .venv.",
                                      "Execute pelo instalar_onponto.bat (ou instalar_onponto.sh).")
            registro("ok")

            modo, _origem = preparar_e_instalar(registro, projeto, base, recriar)

            registro("[6/6] Atalho \"On Ponto\" na Área de Trabalho... ", fim="")
            if not atalho:
                registro("não solicitado")
            elif criar_atalho(registro, projeto):
                registro("ok")
            else:
                registro("não foi possível (use o iniciar_onponto)" if WINDOWS else "não se aplica")
        registro("")
        registro(f"Instalação concluída em {int(time.monotonic() - inicio)} s ({modo}).")
        registro("Para abrir o On Ponto, use o atalho \"On Ponto\" ou o iniciar_onponto."
                 if WINDOWS else "Para abrir o On Ponto, execute ./iniciar_onponto.sh.")
        registro(f"Registro: {caminho_log}")
        registro.fechar()
        return 0
    except FalhaInstalacao as falha:
        registro("FALHOU")
        registro("")
        registro(f"ERRO: {falha}")
        if falha.dica:
            registro(f"O que fazer: {falha.dica}")
        if falha.saida:
            registro("Últimas mensagens:")
            registro(ultimas_linhas(falha.saida))
    except KeyboardInterrupt:
        registro("")
        registro("Instalação interrompida.")
    except Exception:  # noqa: BLE001 - registra qualquer imprevisto antes de sair
        registro.detalhe(traceback.format_exc())
        registro("FALHOU")
        registro("")
        registro("ERRO inesperado durante a instalação.")
    finally:
        podar_logs(projeto)
    registro(f"Registro completo: {caminho_log} (envie ao suporte se precisar de ajuda).")
    registro.fechar()
    return 1


def preparar_console() -> None:
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    preparar_console()
    if sys.version_info[:2] < PYTHON_MINIMO:
        print(f"ERRO: o On Ponto precisa do Python {PYTHON_MINIMO[0]}.{PYTHON_MINIMO[1]} ou mais novo.")
        return 1
    parser = argparse.ArgumentParser(description="Instala ou repara o ambiente do On Ponto.")
    parser.add_argument("--recriar", action="store_true", help="refaz a .venv do zero")
    parser.add_argument("--sem-atalho", action="store_true", help="não cria o atalho na Área de Trabalho")
    parser.add_argument("--verificar", action="store_true", help="só informa se o ambiente está pronto (0) ou não (1)")
    parser.add_argument("--gerar-manifesto", action="store_true", help="manutenção: atualiza SHA256SUMS.txt e constraints.txt")
    args = parser.parse_args(argv)
    projeto = Projeto(Path(__file__).resolve().parents[1])
    if args.verificar:
        pronto, motivo = verificar(projeto)
        print(motivo)
        return 0 if pronto else 1
    if args.gerar_manifesto:
        try:
            pacotes, restricoes = gerar_manifesto(projeto)
        except FalhaInstalacao as falha:
            print(f"ERRO: {falha} {falha.dica}")
            return 1
        print(f"Manifesto gerado: {pacotes} pacotes, {restricoes} versões travadas.")
        return 0
    return instalar(projeto, recriar=args.recriar, atalho=not args.sem_atalho)


if __name__ == "__main__":
    sys.exit(main())
