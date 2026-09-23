#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for Optic Terminal.
#
# Kept as a script rather than an inline install string because it has to install
# one system package before it can build the venv, and a multi-step apt+venv+pip
# sequence is easier to read and to keep idempotent here.
set -euo pipefail
cd "$(dirname "$0")/.."

# python3.12-venv: the base image ships python3.12 but not its ensurepip/venv
# module, so `python3 -m venv` fails with "ensurepip is not available" without
# it. Guarded so a warm snapshot that already has it does no apt work.
if ! dpkg -s python3.12-venv >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3.12-venv
fi

# Recreate the venv only when it is missing, so a rerun against a prepared
# snapshot is a no-op rather than a rebuild.
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip -q
.venv/bin/python -m pip install -q -r requirements.txt

# pytest and httpx are test-only and deliberately absent from requirements.txt,
# which is runtime-only. The suite needs pytest, and FastAPI's TestClient needs
# httpx; without them `python -m pytest` reports "No module named pytest".
.venv/bin/python -m pip install -q pytest httpx
