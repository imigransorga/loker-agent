"""Jalankan Scout tanpa dashboard (cocok untuk cron tiap pagi).

Contoh:  .venv/bin/python scout_cli.py
         .venv/bin/python scout_cli.py '{"roles": ["QA", "backend"], "news": false}'
"""
import json
import sys

from app import db
from app.agents import scout

db.init_db()
payload = scout.normalize_payload(json.loads(sys.argv[1]) if len(sys.argv) > 1 else {})
run_id = db.create_run("scout", payload)
scout.run(run_id, payload)
r = db.get_run(run_id)
print(r["log"])
print("Status:", r["status"], r["stats"])
