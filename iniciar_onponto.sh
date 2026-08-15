#!/usr/bin/env bash

set -u

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || {
    printf '%s\n' "ERRO: Não foi possível localizar a pasta do On Ponto." >&2
    exit 1
}

VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
LOG_DIR="$SCRIPT_DIR/logs"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
FRONTEND_URL="http://127.0.0.1:5500/"
API_URL="http://127.0.0.1:8000/"
BACKEND_PID=""
FRONTEND_PID=""
USE_PROCESS_GROUPS=false

if [[ ! -x "$VENV_PYTHON" ]]; then
    printf '%s\n' "Ambiente do On Ponto não encontrado. Execute ./instalar_onponto.sh primeiro." >&2
    exit 1
fi

if [[ ! -f "$BACKEND_DIR/app/main.py" ]]; then
    printf '%s\n' "ERRO: O backend do On Ponto não foi encontrado." >&2
    exit 1
fi

if [[ ! -f "$FRONTEND_DIR/index.html" ]]; then
    printf '%s\n' "ERRO: O frontend do On Ponto não foi encontrado." >&2
    exit 1
fi

if ! "$VENV_PYTHON" -c 'import fastapi, openpyxl, sqlalchemy, uvicorn, multipart' >/dev/null 2>&1; then
    printf '%s\n' "ERRO: As dependências do On Ponto não estão instaladas corretamente." >&2
    printf '%s\n' "Execute ./instalar_onponto.sh novamente." >&2
    exit 1
fi

porta_livre() {
    "$VENV_PYTHON" - "$1" <<'PY'
import errno
import socket
import sys

porta = int(sys.argv[1])
sock = None
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", porta))
except OSError as erro:
    if erro.errno == errno.EADDRINUSE:
        raise SystemExit(1)
    print(f"Não foi possível verificar a porta {porta}: {erro}", file=sys.stderr)
    raise SystemExit(2)
finally:
    if sock is not None:
        sock.close()
PY
}

aguardar_url() {
    "$VENV_PYTHON" - "$1" "$2" <<'PY'
import sys
import time
import urllib.request

url = sys.argv[1]
limite = time.monotonic() + float(sys.argv[2])
while time.monotonic() < limite:
    try:
        with urllib.request.urlopen(url, timeout=1) as resposta:
            if 200 <= resposta.status < 400:
                raise SystemExit(0)
    except Exception:
        time.sleep(0.25)
raise SystemExit(1)
PY
}

mostrar_fim_log() {
    local arquivo="$1"
    if [[ -s "$arquivo" ]]; then
        printf '\nÚltimas mensagens de %s:\n' "$arquivo" >&2
        tail -n 20 "$arquivo" >&2
    fi
}

encerrar_servicos() {
    local codigo=$?
    trap - EXIT INT TERM HUP
    encerrar_processo "$FRONTEND_PID"
    encerrar_processo "$BACKEND_PID"
    exit "$codigo"
}

processo_ativo() {
    local pid="$1"
    if [[ -z "$pid" ]]; then
        return 1
    fi
    if [[ "$USE_PROCESS_GROUPS" == true ]]; then
        kill -0 -- "-$pid" 2>/dev/null
    else
        kill -0 "$pid" 2>/dev/null
    fi
}

enviar_sinal() {
    local sinal="$1"
    local pid="$2"
    if [[ "$USE_PROCESS_GROUPS" == true ]]; then
        kill "-$sinal" -- "-$pid" 2>/dev/null || true
    else
        kill "-$sinal" "$pid" 2>/dev/null || true
    fi
}

encerrar_processo() {
    local pid="$1"
    local tentativa
    if [[ -z "$pid" ]]; then
        return
    fi
    if processo_ativo "$pid"; then
        enviar_sinal TERM "$pid"
        for tentativa in {1..50}; do
            if ! processo_ativo "$pid"; then
                break
            fi
            sleep 0.1
        done
        if processo_ativo "$pid"; then
            enviar_sinal KILL "$pid"
        fi
    fi
    wait "$pid" 2>/dev/null || true
}

trap 'exit 0' INT TERM HUP
trap encerrar_servicos EXIT

porta_livre 8000
PORTA_STATUS=$?
if [[ "$PORTA_STATUS" -ne 0 ]]; then
    if [[ "$PORTA_STATUS" -eq 1 ]]; then
        printf '%s\n' "ERRO: A porta 8000 já está ocupada." >&2
        printf '%s\n' "Feche o programa que usa essa porta e tente novamente." >&2
    else
        printf '%s\n' "ERRO: Não foi possível verificar a porta 8000." >&2
    fi
    exit 1
fi

porta_livre 5500
PORTA_STATUS=$?
if [[ "$PORTA_STATUS" -ne 0 ]]; then
    if [[ "$PORTA_STATUS" -eq 1 ]]; then
        printf '%s\n' "ERRO: A porta 5500 já está ocupada." >&2
        printf '%s\n' "Feche o programa que usa essa porta e tente novamente." >&2
    else
        printf '%s\n' "ERRO: Não foi possível verificar a porta 5500." >&2
    fi
    exit 1
fi

if ! mkdir -p "$LOG_DIR"; then
    printf '%s\n' "ERRO: Não foi possível criar a pasta de logs em $LOG_DIR." >&2
    exit 1
fi
if ! : >"$BACKEND_LOG" || ! : >"$FRONTEND_LOG"; then
    printf '%s\n' "ERRO: Não foi possível preparar os arquivos de log em $LOG_DIR." >&2
    exit 1
fi

if command -v setsid >/dev/null 2>&1; then
    USE_PROCESS_GROUPS=true
fi

printf '%s\n' "Iniciando API..."
(
    cd -- "$BACKEND_DIR" || exit 1
    if [[ "$USE_PROCESS_GROUPS" == true ]]; then
        exec setsid "$VENV_PYTHON" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
    fi
    exec "$VENV_PYTHON" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
) >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

printf '%s\n' "Iniciando frontend..."
(
    cd -- "$FRONTEND_DIR" || exit 1
    if [[ "$USE_PROCESS_GROUPS" == true ]]; then
        exec setsid "$VENV_PYTHON" -m http.server 5500 --bind 127.0.0.1
    fi
    exec "$VENV_PYTHON" -m http.server 5500 --bind 127.0.0.1
) >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

printf '%s\n' "Aguardando os serviços iniciarem..."
if ! aguardar_url "$API_URL" 15; then
    printf '%s\n' "ERRO: A API não respondeu em http://127.0.0.1:8000." >&2
    mostrar_fim_log "$BACKEND_LOG"
    exit 1
fi

if ! aguardar_url "$FRONTEND_URL" 10; then
    printf '%s\n' "ERRO: O frontend não respondeu em http://127.0.0.1:5500." >&2
    mostrar_fim_log "$FRONTEND_LOG"
    exit 1
fi

if [[ -z "${ONPONTO_NO_BROWSER:-}" ]] && command -v xdg-open >/dev/null 2>&1 && [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    xdg-open "$FRONTEND_URL" >/dev/null 2>&1 &
else
    printf '%s\n' "Abra o navegador em $FRONTEND_URL"
fi

printf '\n%s\n' "On Ponto iniciado"
printf '\nFrontend:\n%s\n' "http://127.0.0.1:5500"
printf '\nAPI:\n%s\n' "http://127.0.0.1:8000"
printf '\nSwagger:\n%s\n' "http://127.0.0.1:8000/docs"
printf '\n%s\n' "Logs: $LOG_DIR"
printf '%s\n' "Pressione Ctrl+C para encerrar os serviços."

while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
    sleep 1
done

if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    printf '%s\n' "ERRO: A API foi encerrada inesperadamente." >&2
    mostrar_fim_log "$BACKEND_LOG"
else
    printf '%s\n' "ERRO: O frontend foi encerrado inesperadamente." >&2
    mostrar_fim_log "$FRONTEND_LOG"
fi
exit 1
