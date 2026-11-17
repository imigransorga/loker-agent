"""Agent 4 — ANALYST: statistik loker yang di-scrape & progres lamaran."""
import json
from collections import Counter

from .. import db, llm
from ..config import claude_enabled


def stats() -> dict:
    total = db.query("SELECT COUNT(*) n FROM jobs")[0]["n"]
    today = db.query("SELECT COUNT(*) n FROM jobs WHERE date(scraped_at)=date('now','localtime')")[0]["n"]
    week = db.query("SELECT COUNT(*) n FROM jobs WHERE scraped_at >= datetime('now','localtime','-7 days')")[0]["n"]
    high = db.query("SELECT COUNT(*) n FROM jobs WHERE relevance >= 70")[0]["n"]

    status_rows = db.query("SELECT status, COUNT(*) n FROM jobs GROUP BY status")
    by_status = {r["status"]: r["n"] for r in status_rows}
    applied = sum(by_status.get(s, 0) for s in ("dilamar", "interview", "ditolak", "diterima"))
    interview = by_status.get("interview", 0) + by_status.get("diterima", 0)

    per_day = db.query(
        """SELECT date(scraped_at) d, COUNT(*) n FROM jobs
           WHERE scraped_at >= datetime('now','localtime','-30 days') GROUP BY d ORDER BY d""")
    by_source = db.query("SELECT source, COUNT(*) n FROM jobs GROUP BY source ORDER BY n DESC")
    by_cat = db.query(
        "SELECT COALESCE(role_category,'Lainnya') c, COUNT(*) n FROM jobs GROUP BY c ORDER BY n DESC")
    by_level = db.query(
        "SELECT COALESCE(level,'tidak jelas') l, COUNT(*) n FROM jobs GROUP BY l ORDER BY n DESC")
    top_companies = db.query(
        """SELECT company, COUNT(*) n FROM jobs WHERE company IS NOT NULL AND company != ''
           GROUP BY company ORDER BY n DESC LIMIT 10""")

    skills = Counter()
    for r in db.query("SELECT skills FROM jobs WHERE COALESCE(relevance,0) >= 50"):
        for s in json.loads(r["skills"] or "[]"):
            skills[s.strip()] += 1
    runs = db.list_runs("scout", 10)

    return {
        "total": total, "today": today, "week": week, "high": high,
        "applied": applied, "interview": interview,
        "response_rate": round(interview / applied * 100) if applied else 0,
        "by_status": by_status,
        "per_day": per_day, "by_source": by_source, "by_category": by_cat,
        "by_level": by_level, "top_companies": top_companies,
        "top_skills": skills.most_common(15),
        "runs": [{**r, "stats": json.loads(r["stats"] or "{}")} for r in runs],
    }


def insight() -> str:
    if not claude_enabled():
        raise llm.ClaudeError("Insight AI butuh ANTHROPIC_API_KEY")
    s = stats()
    s.pop("runs", None)
    return llm.ask_text(
        "Kamu agent Analyst, career coach & analis data pasar kerja IT untuk fresh graduate/junior "
        "di Indonesia. Jawab dalam Bahasa Indonesia, markdown, ringkas dan actionable.",
        "Berikut statistik loker yang sudah dikumpulkan dan progres lamaran saya (JSON):\n"
        + json.dumps(s, ensure_ascii=False)
        + "\n\nBerikan: 1) ringkasan kondisi (3 poin), 2) skill yang paling layak saya prioritaskan "
          "belajar/ditonjolkan di CV, 3) evaluasi funnel lamaran (apply → interview) & saran perbaikan, "
          "4) 3 aksi konkret untuk minggu ini. Jika data masih sedikit, katakan terus terang.",
    )
