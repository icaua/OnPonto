#!/usr/bin/env bash
# On Ponto - instalador (Linux).
# Encontra um Python 3.10+ e entrega o resto para setup/instalar_onponto.py:
# .venv, bibliotecas, teste com uma cópia dos dados. Os pacotes de setup/wheels
# são para Windows; aqui as bibliotecas vêm da internet, nas versões testadas.

set -u

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || {
    printf '%s\n' "ERRO: Não foi possível localizar a pasta do On Ponto." >&2
    exit 1
}

if [[ ! -f "$SCRIPT_DIR/setup/instalar_onponto.py" || ! -f "$SCRIPT_DIR/backend/requirements.txt" ]]; then
    printf '%s\n' "ERRO: Esta pasta do On Ponto está incompleta. Copie-a de novo, completa." >&2
    exit 1
fi

export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
unset PYTHONHOME PYTHONPATH

PYTHON=""
for candidato in python3.12 python3.13 python3.11 python3.10 python3; do
    if command -v "$candidato" >/dev/null 2>&1 \
        && "$candidato" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
        PYTHON="$(command -v "$candidato")"
        break
    fi
done

if [[ -z "$PYTHON" ]]; then
    printf '%s\n' "ERRO: Python 3.10 ou superior não foi encontrado." >&2
    printf '%s\n' "Instale com o gerenciador da sua distribuição (ex.: sudo apt install python3 python3-venv)." >&2
    exit 1
fi

exec "$PYTHON" "$SCRIPT_DIR/setup/instalar_onponto.py" "$@"
