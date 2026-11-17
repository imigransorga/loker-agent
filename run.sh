#!/bin/zsh
# Jalankan dashboard: ./run.sh  lalu buka http://127.0.0.1:8800
cd "$(dirname "$0")"
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -r requirements.txt; }
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8800 --reload
