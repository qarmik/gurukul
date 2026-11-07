#!/bin/bash
# Double-click from Finder; no automatic interpreter installation or fallback.
set -e
GURUKUL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GURUKUL_PYTHON="${GURUKUL_PYTHON:-$GURUKUL_ROOT/.venv/bin/python}"
if ! test -x "$GURUKUL_PYTHON"; then
  printf 'Set GURUKUL_PYTHON to an installed Python 3.11+ interpreter, or install this project into .venv.\n'
  read -r -p 'Press Enter to close.' unused
  exit 1
fi
export PYTHONPATH="$GURUKUL_ROOT/src"
exec "$GURUKUL_PYTHON" -B -m gurukul.workspace --root "$GURUKUL_ROOT"
