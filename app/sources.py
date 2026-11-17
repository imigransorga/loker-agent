"""Sumber loker lewat API publik resmi (tanpa scraping HTML, aman dari banned).

- Remotive  : https://remotive.com/api/remote-jobs
- RemoteOK  : https://remoteok.com/api  (wajib cantumkan sumber + link balik -> ditampilkan di dashboard)
- Arbeitnow : https://www.arbeitnow.com/api/job-board-api

Loker Indonesia (Glints, Kalibrr, JobStreet, dll) dicari lewat web search Claude di agents/scout.py.
"""
import hashlib
import html
import json
import re
import urllib.parse
import ssl
import urllib.request
from datetime import datetime, timezone

import certifi

UA = "Mozilla/5.0 (loker-agent personal job scout)"
SSL_CTX = ssl.create_default_context(cafile=certifi.where())

# Lokasi remote yang masih bisa dilamar dari Indonesia
OPEN_LOCATIONS = ["worldwide", "anywhere", "global", "asia", "apac", "indonesia",
                  "southeast asia", "sea", "remote"]


def _get_json(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def strip_html(s: str | None, limit: int = 4000) -> str:
    if not s:
        return ""
    s = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()[:limit]


def make_uid(source: str, key: str) -> str:
    return hashlib.sha1(f"{source}|{key}".encode()).hexdigest()


def _iso(ts) -> str | None:
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        if isinstance(ts, str) and ts:
            return ts[:10]
    except Exception:
        pass
    return None


def fetch_remotive(search: str | None = None) -> list[dict]:
    url = "https://remotive.com/api/remote-jobs?category=software-dev&limit=300"
    if search:
        url += "&search=" + urllib.parse.quote(search)
    data = _get_json(url)
    out = []
    for j in data.get("jobs", []):
        out.append({
            "uid": make_uid("remotive", str(j.get("id"))),
            "source": "Remotive",
            "title": j.get("title", "").strip(),
            "company": j.get("company_name"),
            "location": j.get("candidate_required_location") or "Remote",
            "remote": True,
            "url": j.get("url"),
            "description": strip_html(j.get("description")),
            "tags": j.get("tags") or [],
            "posted_at": _iso(j.get("publication_date")),
        })
    return out


def fetch_remoteok() -> list[dict]:
    data = _get_json("https://remoteok.com/api")
    out = []
    for j in data:
        if not isinstance(j, dict) or "position" not in j:
            continue  # elemen pertama = legal notice
        out.append({
            "uid": make_uid("remoteok", str(j.get("id"))),
            "source": "RemoteOK",
            "title": (j.get("position") or "").strip(),
            "company": j.get("company"),
            "location": j.get("location") or "Remote",
            "remote": True,
            "url": j.get("url") or j.get("apply_url"),
            "description": strip_html(j.get("description")),
            "tags": j.get("tags") or [],
            "posted_at": _iso(j.get("date") or j.get("epoch")),
        })
    return out


def fetch_arbeitnow(pages: int = 2) -> list[dict]:
    out = []
    for p in range(1, pages + 1):
        data = _get_json(f"https://www.arbeitnow.com/api/job-board-api?page={p}")
        for j in data.get("data", []):
            if not j.get("remote"):
                continue  # non-remote = harus di Jerman
            out.append({
                "uid": make_uid("arbeitnow", j.get("slug", "")),
                "source": "Arbeitnow",
                "title": (j.get("title") or "").strip(),
                "company": j.get("company_name"),
                "location": j.get("location") or "Remote",
                "remote": True,
                "url": j.get("url"),
                "description": strip_html(j.get("description")),
                "tags": j.get("tags") or [],
                "posted_at": _iso(j.get("created_at")),
            })
    return out


API_SOURCES = {
    "remotive": fetch_remotive,
    "remoteok": fetch_remoteok,
    "arbeitnow": fetch_arbeitnow,
}


# ---------------- filter ----------------
def _has_any(text: str, words: list[str]) -> bool:
    t = f" {text.lower()} "
    for w in words:
        w = w.lower().strip()
        if not w:
            continue
        # cocokkan sebagai kata utuh supaya "qa" tidak cocok dengan "aqua"
        if re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", t):
            return True
    return False


def is_relevant_title(title: str, roles: list[str], senior_words: list[str]) -> bool:
    return _has_any(title, roles) and not _has_any(title, senior_words)


def is_senior(title: str, senior_words: list[str]) -> bool:
    return _has_any(title, senior_words)


def is_open_location(location: str) -> bool:
    loc = (location or "").lower()
    return not loc or any(k in loc for k in OPEN_LOCATIONS)


def categorize(title: str, categories: dict[str, list[str]]) -> str:
    for cat, words in categories.items():
        if _has_any(title, words):
            return cat
    return "Lainnya"


def rule_score(job: dict, levels: list[str]) -> tuple[int, str]:
    """Skor kasar tanpa AI: dipakai bila API key Claude belum diisi."""
    text = f"{job['title']} {job.get('description', '')[:1500]}".lower()
    score = 50
    reasons = []
    if _has_any(job["title"], levels + ["jr", "graduate", "trainee"]):
        score += 30
        reasons.append("judul menyebut level junior/fresh grad")
    elif _has_any(text, levels + ["0-2 years", "1-2 years", "no experience"]):
        score += 15
        reasons.append("deskripsi menyebut level pemula")
    if re.search(r"\b([4-9]|1\d)\+?\s*(years|tahun)", text):
        score -= 25
        reasons.append("minta pengalaman 4+ tahun")
    if "indonesia" in text:
        score += 10
        reasons.append("menyebut Indonesia")
    return max(0, min(100, score)), "; ".join(reasons) or "cocok dari judul posisi"
