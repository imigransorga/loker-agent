"""Agent 1 — SCOUT: cari loker IT terbaru yang relevan + berita pasar kerja.

Payload contoh (POST /api/scout/run):
{
  "roles": ["QA", "frontend", "backend", "web developer", "software engineer"],
  "levels": ["fresh graduate", "junior"],
  "locations": ["Indonesia", "Bandung", "Jakarta", "Remote"],
  "sources": ["remotive", "remoteok", "arbeitnow", "web_id"],
  "web_limit": 15,          # maks loker Indonesia dari web search Claude
  "ai_score_limit": 40,     # maks loker baru yang dinilai Claude (hemat biaya)
  "news": true              # sekalian cari berita pasar kerja IT
}
"""
import re
import traceback

from .. import db, llm, sources
from ..config import (DEFAULT_LEVELS, DEFAULT_LOCATIONS, DEFAULT_ROLES, ROLE_CATEGORIES,
                      SENIOR_WORDS, SKILL_KEYWORDS, claude_enabled)

ID_JOB_SITES = ["glints.com", "kalibrr.com", "jobstreet.co.id", "id.jobstreet.com",
                "linkedin.com", "dealls.com", "karir.com", "loker.id", "kitalulus.com",
                "techinasia.com", "id.indeed.com"]

SCOUT_SYSTEM = (
    "Kamu adalah agent Scout, asisten pencari lowongan kerja IT untuk fresh graduate dan "
    "junior di Indonesia. Kamu teliti, hanya melaporkan lowongan yang benar-benar kamu temukan "
    "di hasil pencarian (jangan mengarang URL atau perusahaan), dan menulis dalam Bahasa Indonesia."
)

JOBS_SCHEMA = {
    "type": "object",
    "properties": {
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "location": {"type": "string"},
                    "url": {"type": "string"},
                    "posted": {"type": "string", "description": "tanggal/umur posting jika diketahui, '' bila tidak"},
                    "site": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["title", "company", "location", "url", "posted", "site", "summary"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["jobs"],
    "additionalProperties": False,
}

SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "relevance": {"type": "integer", "description": "0-100"},
                    "level": {"type": "string", "enum": ["intern", "fresh graduate", "junior", "mid", "senior", "tidak jelas"]},
                    "category": {"type": "string", "enum": list(ROLE_CATEGORIES.keys()) + ["Lainnya"]},
                    "reason": {"type": "string"},
                    "skills": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "relevance", "level", "category", "reason", "skills"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}

NEWS_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "url": {"type": "string"},
                },
                "required": ["title", "summary", "url"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def normalize_payload(p: dict) -> dict:
    def as_list(v, default):
        if isinstance(v, str):
            v = [x.strip() for x in re.split(r"[,\n]", v) if x.strip()]
        return v or default

    return {
        "roles": as_list(p.get("roles"), DEFAULT_ROLES),
        "levels": as_list(p.get("levels"), DEFAULT_LEVELS),
        "locations": as_list(p.get("locations"), DEFAULT_LOCATIONS),
        "sources": as_list(p.get("sources"), ["remotive", "remoteok", "arbeitnow", "web_id"]),
        "web_limit": max(0, min(30, int(p.get("web_limit") or 15))),
        "ai_score_limit": max(0, min(150, int(p.get("ai_score_limit") or 40))),
        "news": str(p.get("news", True)).lower() in ("1", "true", "on", "yes"),
    }


def extract_skills(text: str) -> list[str]:
    found = []
    low = text.lower()
    for s in SKILL_KEYWORDS:
        if re.search(r"(?<![a-z0-9])" + re.escape(s.lower()) + r"(?![a-z0-9])", low):
            found.append(s)
    return found[:12]


def run(run_id: int, payload: dict):
    p = normalize_payload(payload)
    stats = {"fetched": 0, "relevant": 0, "new": 0, "duplicate": 0, "ai_scored": 0,
             "news": 0, "per_source": {}, "errors": []}
    new_ids: list[int] = []

    def log(msg):
        db.log_run(run_id, msg)

    try:
        # 1) Sumber API publik
        for name in p["sources"]:
            if name not in sources.API_SOURCES:
                continue
            try:
                log(f"Mengambil loker dari {name}…")
                items = sources.API_SOURCES[name]()
            except Exception as e:  # satu sumber gagal jangan hentikan semuanya
                stats["errors"].append(f"{name}: {e}")
                log(f"⚠️ {name} gagal: {e}")
                continue
            stats["fetched"] += len(items)
            rel = [j for j in items
                   if sources.is_relevant_title(j["title"], p["roles"], SENIOR_WORDS)
                   and sources.is_open_location(j["location"])]
            added = _save(rel, run_id, new_ids, stats)
            stats["per_source"][name] = {"fetched": len(items), "relevant": len(rel), "new": added}
            log(f"{name}: {len(items)} loker, {len(rel)} relevan, {added} baru")

        # 2) Loker Indonesia lewat web search Claude
        if "web_id" in p["sources"]:
            if not claude_enabled():
                log("Lewati pencarian loker Indonesia (butuh ANTHROPIC_API_KEY)")
            elif p["web_limit"]:
                try:
                    _search_indonesia(p, run_id, new_ids, stats, log)
                except Exception as e:
                    stats["errors"].append(f"web_id: {e}")
                    log(f"⚠️ Pencarian loker Indonesia gagal: {e}")

        # 3) Penilaian relevansi
        _score(new_ids, p, stats, log)

        # 4) Berita pasar kerja
        if p["news"] and claude_enabled():
            try:
                _news(p, run_id, stats, log)
            except Exception as e:
                stats["errors"].append(f"news: {e}")
                log(f"⚠️ Pencarian berita gagal: {e}")

        log(f"Selesai ✅ {stats['new']} loker baru dari {stats['fetched']} yang dicek.")
        db.finish_run(run_id, "done", stats)
    except Exception as e:
        log(f"❌ Error: {e}\n{traceback.format_exc()}")
        stats["errors"].append(str(e))
        db.finish_run(run_id, "error", stats)


def _save(items: list[dict], run_id: int, new_ids: list[int], stats: dict) -> int:
    added = 0
    for j in items:
        j["run_id"] = run_id
        j["role_category"] = sources.categorize(j["title"], ROLE_CATEGORIES)
        stats["relevant"] += 1
        jid = db.insert_job(j)
        if jid:
            new_ids.append(jid)
            added += 1
            stats["new"] += 1
        else:
            stats["duplicate"] += 1
    return added


def _search_indonesia(p, run_id, new_ids, stats, log):
    log("Mencari loker Indonesia lewat web search Claude (Glints, Kalibrr, JobStreet, dll)…")
    prompt = (
        f"Cari lowongan kerja TERBARU (maksimal 14 hari terakhir, utamakan yang masih buka) "
        f"untuk posisi: {', '.join(p['roles'][:15])}.\n"
        f"Level: {', '.join(p['levels'])}. Lokasi: {', '.join(p['locations'])}.\n"
        f"Cari di portal loker Indonesia seperti {', '.join(ID_JOB_SITES)} dan halaman karier perusahaan.\n"
        f"Kumpulkan sampai {p['web_limit']} lowongan berbeda. Untuk tiap lowongan tulis: judul posisi, "
        f"perusahaan, lokasi, URL halaman lowongan (persis dari hasil pencarian), tanggal posting bila ada, "
        f"situs sumber, dan ringkasan kualifikasi singkat. Abaikan posisi senior/lead/manager."
    )
    text, found = llm.research(SCOUT_SYSTEM, prompt, max_searches=8)
    if not text:
        log("Web search tidak mengembalikan hasil")
        return
    known_urls = {s["url"] for s in found}
    data = llm.ask_json(
        SCOUT_SYSTEM,
        "Ubah laporan berikut menjadi daftar lowongan terstruktur. Hanya masukkan lowongan yang "
        "punya URL. Jangan menambah data yang tidak ada di laporan.\n\n" + text,
        JOBS_SCHEMA,
    )
    items = []
    for j in data.get("jobs", [])[: p["web_limit"]]:
        url = (j.get("url") or "").strip()
        if not url.startswith("http"):
            continue
        if sources.is_senior(j["title"], SENIOR_WORDS):
            continue
        site = j.get("site") or re.sub(r"^https?://(www\.)?([^/]+).*", r"\2", url)
        items.append({
            "uid": sources.make_uid("web", url.split("?")[0].rstrip("/")),
            "source": f"Web: {site}",
            "title": j["title"],
            "company": j.get("company"),
            "location": j.get("location") or "Indonesia",
            "remote": "remote" in (j.get("location") or "").lower(),
            "url": url,
            "description": j.get("summary", ""),
            "tags": ["verified-url"] if url in known_urls else [],
            "posted_at": j.get("posted") or None,
        })
    added = _save(items, run_id, new_ids, stats)
    stats["per_source"]["web_id"] = {"fetched": len(data.get("jobs", [])), "relevant": len(items), "new": added}
    log(f"Web search: {len(items)} loker Indonesia ditemukan, {added} baru")


def _score(new_ids, p, stats, log):
    if not new_ids:
        return
    jobs = db.jobs_by_ids(new_ids)
    # skor kasar dulu untuk semua
    for j in jobs:
        sc, why = sources.rule_score(j, p["levels"])
        j["_rule"] = sc
        db.update_job_analysis(j["id"], sc, "tidak jelas", f"(otomatis) {why}",
                               extract_skills(f"{j['title']} {' '.join(j['tags'])} {j.get('description') or ''}"))
    if not claude_enabled() or not p["ai_score_limit"]:
        log(f"{len(jobs)} loker dinilai dengan aturan sederhana (isi API key untuk penilaian AI)")
        return

    targets = sorted(jobs, key=lambda j: j["_rule"], reverse=True)[: p["ai_score_limit"]]
    log(f"Claude menilai kecocokan {len(targets)} loker…")
    for i in range(0, len(targets), 10):
        batch = targets[i:i + 10]
        listing = "\n\n".join(
            f"[id={j['id']}] {j['title']} — {j.get('company') or '-'} ({j.get('location') or '-'})\n"
            f"Tag: {', '.join(j['tags'][:10])}\n{(j.get('description') or '')[:1500]}"
            for j in batch
        )
        try:
            res = llm.ask_json(
                SCOUT_SYSTEM,
                "Nilai seberapa cocok tiap lowongan untuk kandidat FRESH GRADUATE / JUNIOR dari "
                "Indonesia (bisa remote). relevance 0-100: tinggi bila level pemula & bisa dilamar dari "
                "Indonesia; rendah bila minta pengalaman bertahun-tahun, senior, atau lokasi terkunci "
                "negara lain. Tulis reason singkat (1 kalimat, Bahasa Indonesia) dan skills teknis "
                "utama yang diminta (maks 8).\n\n" + listing,
                SCORE_SCHEMA,
            )
        except llm.ClaudeError as e:
            stats["errors"].append(f"score: {e}")
            log(f"⚠️ Penilaian AI gagal: {e}")
            return
        valid = {j["id"] for j in batch}
        for r in res.get("results", []):
            if r["id"] in valid:
                db.update_job_analysis(r["id"], max(0, min(100, r["relevance"])), r["level"],
                                       r["reason"], r["skills"][:8], r["category"])
                stats["ai_scored"] += 1
    log(f"Claude selesai menilai {stats['ai_scored']} loker")


def _news(p, run_id, stats, log):
    log("Mencari berita pasar kerja IT terbaru…")
    text, _ = llm.research(
        SCOUT_SYSTEM,
        "Cari berita/informasi TERBARU (30 hari terakhir) yang berguna untuk fresh graduate & junior "
        f"yang melamar posisi {', '.join(p['roles'][:8])} di Indonesia: perusahaan yang sedang "
        "hiring besar-besaran, program magang/trainee/MT IT, layoff di startup, tren skill yang dicari, "
        "dan job fair. Sertakan URL sumber tiap berita.",
        max_searches=5,
    )
    data = llm.ask_json(
        SCOUT_SYSTEM,
        "Ubah laporan berikut menjadi maksimal 8 berita (judul, ringkasan 1-2 kalimat, URL sumber). "
        "Jangan menambah info yang tidak ada di laporan.\n\n" + text,
        NEWS_SCHEMA,
    )
    for n in data.get("items", [])[:8]:
        db.insert_news(run_id, "pasar kerja IT", n["title"], n["summary"], n["url"])
        stats["news"] += 1
    log(f"{stats['news']} berita tersimpan")


COMPANY_SYSTEM = (
    "Kamu agent Scout yang membantu kandidat junior meriset perusahaan sebelum melamar. "
    "Tulis ringkas dalam Bahasa Indonesia (markdown), sertakan link sumber, dan bedakan fakta vs dugaan."
)


def research_company(job_id: int) -> str:
    job = db.get_job(job_id)
    if not job:
        raise ValueError("Loker tidak ditemukan")
    text, found = llm.research(
        COMPANY_SYSTEM,
        f"Riset perusahaan '{job.get('company')}' untuk lowongan '{job['title']}' ({job.get('location')}).\n"
        "Buat ringkasan: 1) profil singkat & produk, 2) berita/kabar terbaru (funding, layoff, ekspansi), "
        "3) review karyawan/budaya kerja bila ada, 4) red flag yang perlu diwaspadai (termasuk "
        "kemungkinan loker palsu/penipuan), 5) tips menyesuaikan CV & persiapan interview untuk posisi ini.",
        max_searches=5,
    )
    if found:
        text += "\n\n**Sumber:**\n" + "\n".join(f"- [{s['title'] or s['url']}]({s['url']})" for s in found[:10])
    db.save_research(job_id, job.get("company") or "", text)
    return text
