"""Agent FAMILY — Pusat Info: brief harian (tanpa AI, gratis)."""
from datetime import datetime, timedelta

from .. import db

FOLLOW_UP_DAYS = 7


def brief() -> dict:
    since = (datetime.now() - timedelta(hours=24)).isoformat(timespec="seconds")
    new_jobs = db.query(
        """SELECT id, title, company, location, relevance FROM jobs
           WHERE scraped_at >= ? ORDER BY COALESCE(relevance,0) DESC LIMIT 5""", (since,))
    new_count = db.query("SELECT COUNT(*) n FROM jobs WHERE scraped_at >= ?", (since,))[0]["n"]

    limit = (datetime.now() - timedelta(days=FOLLOW_UP_DAYS)).isoformat(timespec="seconds")
    follow_up = db.query(
        """SELECT id, title, company, COALESCE(status_changed_at, scraped_at) since FROM jobs
           WHERE status='dilamar' AND COALESCE(status_changed_at, scraped_at) <= ?
           ORDER BY since LIMIT 8""", (limit,))
    for f in follow_up:
        f["days"] = (datetime.now() - datetime.fromisoformat(f["since"])).days

    interviews = db.query(
        "SELECT id, title, company, notes FROM jobs WHERE status='interview' ORDER BY status_changed_at DESC LIMIT 8")
    saved = db.query(
        """SELECT id, title, company, relevance FROM jobs WHERE status='disimpan'
           ORDER BY COALESCE(relevance,0) DESC LIMIT 5""")
    last = db.list_runs("scout", 1)
    hour = datetime.now().hour
    greet = "Selamat pagi" if hour < 11 else "Selamat siang" if hour < 15 else "Selamat sore" if hour < 18 else "Selamat malam"

    tips = []
    if not last:
        tips.append("Scout belum pernah ditugaskan — minta Kia cari loker dulu.")
    elif last[0]["started_at"][:10] != datetime.now().date().isoformat():
        tips.append("Hari ini belum cari loker. Minta Kia jalan sekali biar dapat loker terbaru.")
    if follow_up:
        tips.append(f"Ada {len(follow_up)} lamaran > {FOLLOW_UP_DAYS} hari tanpa kabar — kirim email follow-up singkat.")
    if interviews:
        tips.append("Ada jadwal interview — minta Kayla siapkan latihan pertanyaannya.")
    if saved and not follow_up:
        tips.append(f"{len(saved)} loker sudah disimpan tapi belum dilamar. Yuk lamar yang skornya paling tinggi.")
    if not tips:
        tips.append("Semua aman. Pertahankan ritme: cek loker baru tiap pagi, lamar 3–5 per hari.")

    return {"greet": greet, "new_count": new_count, "new_jobs": new_jobs, "follow_up": follow_up,
            "interviews": interviews, "saved": saved, "news": db.list_news(3), "tips": tips}
