#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Python 3.10/3.11/3.12 have compatible CPU PyTorch wheels; avoid system Python 3.14.
PYTHON_BIN="${PYTHON_BIN:-python3.10}"
"$PYTHON_BIN" -c 'import sys; assert (3,10) <= sys.version_info[:2] <= (3,12), "Use Python 3.10–3.12"'
mkdir -p .runtime
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python -m pip freeze > .runtime/requirements-lock.txt
