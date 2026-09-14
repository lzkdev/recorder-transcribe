#!/usr/bin/env bash
set -euo pipefail
if ! command -v python3 >/dev/null 2>&1; then
  echo 'Python 3.9+ is required. Install Python, then retry (see references/setup.md).' >&2
  exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo 'Python 3.9+ is required; upgrade the python3 executable.' >&2
  exit 1
fi
exec python3 "$(cd "$(dirname "$0")" && pwd)/recorder.py" "$@"
