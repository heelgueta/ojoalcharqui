#!/bin/sh
# ojo al charqui - double-click launcher (macOS / Linux)
cd "$(dirname "$0")" || exit 1
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

if command -v python3 >/dev/null 2>&1; then
    exec python3 run.py
elif command -v python >/dev/null 2>&1; then
    exec python run.py
else
    echo "No se encontro Python. Instalalo desde https://www.python.org/downloads/"
    read -r _ </dev/tty
    exit 1
fi
