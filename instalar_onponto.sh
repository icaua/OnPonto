#!/usr/bin/env bash

set -u

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || {
    printf '%s\n' "ERRO: Não foi possível localizar a pasta do On Ponto." >&2
    exit 1
}

VENV_DIR="$SCRIPT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
REQUIREMENTS="$SCRIPT_DIR/backend/requirements.txt"

if [[ ! -f "$REQUIREMENTS" ]]; then
    printf '%s\n' "ERRO: backend/requirements.txt não foi encontrado." >&2
    exit 1
fi

if [[ -x "$VENV_PYTHON" ]]; then
    if ! "$VENV_PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
        printf '%s\n' "ERRO: O ambiente .venv está danificado ou usa Python anterior ao 3.10." >&2
        printf '%s\n' "Renomeie ou remova a pasta .venv e execute este instalador novamente." >&2
        exit 1
    fi
    printf '%s\n' "Ambiente virtual existente encontrado."
elif [[ -e "$VENV_DIR" ]]; then
    printf '%s\n' "ERRO: A pasta .venv existe, mas não contém bin/python executável." >&2
    printf '%s\n' "Renomeie ou remova a pasta .venv e execute este instalador novamente." >&2
    exit 1
else
    if ! command -v python3 >/dev/null 2>&1; then
        printf '%s\n' "ERRO: Python 3.10 ou superior não foi encontrado." >&2
        printf '%s\n' "Instale o Python 3 da sua distribuição e tente novamente." >&2
        exit 1
    fi
    if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
        printf '%s\n' "ERRO: O On Ponto requer Python 3.10 ou superior." >&2
        exit 1
    fi

    printf '%s\n' "Criando ambiente virtual em .venv..."
    if ! python3 -m venv "$VENV_DIR"; then
        printf '%s\n' "ERRO: Não foi possível criar o ambiente virtual .venv." >&2
        printf '%s\n' "Instale o pacote python3-venv da sua distribuição e tente novamente." >&2
        exit 1
    fi
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
    printf '%s\n' "ERRO: O ambiente virtual não foi criado corretamente." >&2
    printf '%s\n' "Instale o pacote python3-venv da sua distribuição e tente novamente." >&2
    exit 1
fi

if ! "$VENV_PYTHON" -m pip --version >/dev/null 2>&1; then
    printf '%s\n' "ERRO: O ambiente .venv está incompleto e não contém pip." >&2
    printf '%s\n' "Renomeie ou remova a pasta .venv, instale python3-venv e tente novamente." >&2
    exit 1
fi

printf '%s\n' "Instalando dependências do On Ponto..."
if ! "$VENV_PYTHON" -m pip install -r "$REQUIREMENTS"; then
    printf '%s\n' "ERRO: Não foi possível instalar as dependências." >&2
    printf '%s\n' "Verifique sua conexão e as mensagens acima." >&2
    exit 1
fi

printf '\n%s\n' "On Ponto instalado com sucesso."
printf '%s\n' "Execute ./iniciar_onponto.sh para abrir o sistema."
