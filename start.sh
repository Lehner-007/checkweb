#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export CHECKWEB_DEV=1
PYTHON=/usr/bin/python3
if [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then PYTHON="$SCRIPT_DIR/.venv/bin/python"; fi
exec "$PYTHON" "$SCRIPT_DIR/checkweb.py" "$@"
