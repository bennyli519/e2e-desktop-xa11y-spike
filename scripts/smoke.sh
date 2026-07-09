#!/usr/bin/env bash
# Smoke run: auto-login + recording end-to-end (record -> stop -> note ->
# transcript check). One pytest invocation so the session-scoped, logged-in
# Heidi app is reused — the recording flow SKIPS if login hasn't run first,
# so auth is always collected ahead of tests/recording/.
#
# Run from a terminal holding Accessibility + Screen Recording permission
# (e.g. Ghostty), with Heidi installed, frontmost, and on the active Space.
#
# Usage:
#   bash scripts/smoke.sh            # login + 30s recording (fast, default)
#   bash scripts/smoke.sh --full     # login + all recording flows (30s/1/5/10min)
#   bash scripts/smoke.sh -k accuracy  # extra args pass through to pytest
set -euo pipefail

cd "$(dirname "$0")/.."

# Prefer the project venv so `pytest` resolves even without activation.
PYTEST=(pytest)
if [ -x ".venv/bin/python" ]; then
    PYTEST=(.venv/bin/python -m pytest)
elif [ -x ".venv/Scripts/python.exe" ]; then
    PYTEST=(.venv/Scripts/python.exe -m pytest)
elif [ -x ".venv/bin/pytest" ]; then
    PYTEST=(.venv/bin/pytest)
elif [ -x ".venv/Scripts/pytest.exe" ]; then
    PYTEST=(.venv/Scripts/pytest.exe)
fi

MARKER=(-m "not longsession")   # default: skip the 1/5/10-min long sessions
if [ "${1:-}" = "--full" ]; then
    MARKER=()                   # include every recording flow
    shift
fi

# auth first (login), then the recording flows — order is load-bearing.
exec "${PYTEST[@]}" tests/auth/test_login.py tests/recording/ "${MARKER[@]}" -s "$@"
