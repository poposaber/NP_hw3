#!/usr/bin/env bash
VENV_DIR=".venv"
PYTHON=${1:-python3}

set -e
$PYTHON -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV_DIR/bin/python" -m pip install -r requirements.txt
echo "Activate with: source $VENV_DIR/bin/activate"