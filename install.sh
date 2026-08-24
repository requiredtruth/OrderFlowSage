#!/usr/bin/env sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"
python3 -m compileall -q orderflowsage tests
PYTHONPATH=. python3 -m unittest discover -s tests -v
PYTHONPATH=. python3 -m orderflowsage demo
