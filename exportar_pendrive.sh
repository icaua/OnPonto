#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ $# -ne 1 ]; then
    echo "Uso:"
    echo "  ./exportar_pendrive.sh /caminho/do/pendrive"
    echo
    echo "Exemplo:"
    echo "  ./exportar_pendrive.sh /media/$USER/ONPONTO"
    exit 1
fi

DESTINO="$1"
ALVO="$DESTINO/OnPonto"

if [ ! -d "$DESTINO" ]; then
    echo "ERRO: destino não encontrado:"
    echo "  $DESTINO"
    exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
    echo "ERRO: rsync não encontrado."
    exit 1
fi

echo
echo "=========================================="
echo "       ON PONTO - EXPORTAÇÃO LIMPA"
echo "=========================================="
echo
echo "Origem:"
echo "  $ROOT"
echo
echo "Destino:"
echo "  $ALVO"
echo

mkdir -p "$ALVO"

# Remove resíduos de versões anteriores que NÃO devem ir para o pendrive
rm -rf \
    "$ALVO/.git" \
    "$ALVO/.venv" \
    "$ALVO/.venv-linux" \
    "$ALVO/venv" \
    "$ALVO/backend/__pycache__" \
    "$ALVO/backend/.test-data" \
    "$ALVO/frontend/node_modules" \
    "$ALVO/.pytest_cache"

rm -f \
    "$ALVO/backend/onponto.db" \
    "$ALVO/backend/onponto.db-shm" \
    "$ALVO/backend/onponto.db-wal" \
    "$ALVO/backend/onponto.db-journal" \
    "$ALVO/backend/onponto.db.backup-inicial"

# Limpa uploads antigos, mas preserva a pasta
rm -rf "$ALVO/backend/uploads"
mkdir -p "$ALVO/backend/uploads"

rsync -av --delete \
    --exclude='.git/' \
    --exclude='.github/' \
    --exclude='.venv/' \
    --exclude='.venv-linux/' \
    --exclude='venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.pytest_cache/' \
    --exclude='.mypy_cache/' \
    --exclude='.ruff_cache/' \
    --exclude='.coverage' \
    --exclude='htmlcov/' \
    --exclude='node_modules/' \
    --exclude='.DS_Store' \
    --exclude='Thumbs.db' \
    --exclude='backend/onponto.db' \
    --exclude='backend/onponto.db.backup-inicial' \
    --exclude='backend/onponto.db-shm' \
    --exclude='backend/onponto.db-wal' \
    --exclude='backend/onponto.db-journal' \
    --exclude='backend/uploads/*' \
    --exclude='backend/.test-data/' \
    --exclude='fixtures/generated/' \
    --exclude='RELATORIO-ATIVACAO-LINUX.md' \
    --exclude='RELATORIO-TESTES-FUNCIONAIS.md' \
    --exclude='*.log' \
    "$ROOT/" "$ALVO/"

touch "$ALVO/backend/uploads/.gitkeep"

echo
echo "=========================================="
echo " EXPORTAÇÃO CONCLUÍDA"
echo "=========================================="
echo
echo "On Ponto pronto em:"
echo "  $ALVO"
echo
