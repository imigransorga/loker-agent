"""SQLite sederhana: loker, run agent, berita."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT,
    location TEXT,
    remote INTEGER DEFAULT 0,
    url TEXT,
    description TEXT,
    tags TEXT DEFAULT '[]',
    posted_at TEXT,
    scraped_at TEXT NOT NULL,
    run_id INTEGER,
    role_category TEXT,
    level TEXT,
    relevance INTEGER,
    reason TEXT,
    skills TEXT DEFAULT '[]',
    status TEXT DEFAULT 'baru',
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_scraped ON jobs(scraped_at);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,
    payload TEXT,
    status TEXT DEFAULT 'running',
    log TEXT DEFAULT '',
    stats TEXT DEFAULT '{}',
    started_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    topic TEXT,
    title TEXT,
    summary TEXT,
    url TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interview_prep (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER,
    content TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS company_research (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER,
    company TEXT,
    content TEXT,
    created_at TEXT NOT NULL
);
"""

JOB_STATUSES = ["baru", "disimpan", "dilamar", "interview", "ditolak", "diterima", "diabaikan"]


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db():
    with conn() as c:
        c.executescript(SCHEMA)
        cols = {r["name"] for r in c.execute("PRAGMA table_info(jobs)")}
        if "status_changed_at" not in cols:  # migrasi: kapan status lamaran terakhir diubah
            c.execute("ALTER TABLE jobs ADD COLUMN status_changed_at TEXT")


# ---------- runs ----------
def create_run(agent: str, payload: dict) -> int:
    with conn() as c:
        cur = c.execute(
            "INSERT INTO runs(agent, payload, started_at) VALUES (?,?,?)",
            (agent, json.dumps(payload, ensure_ascii=False), now()),
        )
        return cur.lastrowid


def log_run(run_id: int, message: str):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n"
    with conn() as c:
        c.execute("UPDATE runs SET log = log || ? WHERE id=?", (line, run_id))


def finish_run(run_id: int, status: str, stats: dict):
    with conn() as c:
        c.execute(
            "UPDATE runs SET status=?, stats=?, finished_at=? WHERE id=?",
            (status, json.dumps(stats, ensure_ascii=False), now(), run_id),
        )


def get_run(run_id: int):
    with conn() as c:
        r = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return dict(r) if r else None


def list_runs(agent: str | None = None, limit: int = 20):
    with conn() as c:
        if agent:
            rows = c.execute(
                "SELECT * FROM runs WHERE agent=? ORDER BY id DESC LIMIT ?", (agent, limit)
            ).fetchall()
        else:
            rows = c.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


# ---------- jobs ----------
def insert_job(job: dict) -> int | None:
    """Simpan loker; kembalikan id bila baru, None bila duplikat."""
    with conn() as c:
        try:
            cur = c.execute(
                """INSERT INTO jobs(uid, source, title, company, location, remote, url,
                   description, tags, posted_at, scraped_at, run_id, role_category)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    job["uid"], job["source"], job["title"], job.get("company"),
                    job.get("location"), int(bool(job.get("remote"))), job.get("url"),
                    job.get("description"), json.dumps(job.get("tags", []), ensure_ascii=False),
                    job.get("posted_at"), now(), job.get("run_id"), job.get("role_category"),
                ),
            )
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None


def update_job_analysis(job_id: int, relevance: int, level: str, reason: str, skills: list,
                        role_category: str | None = None):
    with conn() as c:
        c.execute(
            """UPDATE jobs SET relevance=?, level=?, reason=?, skills=?,
               role_category=COALESCE(?, role_category) WHERE id=?""",
            (relevance, level, reason, json.dumps(skills, ensure_ascii=False), role_category, job_id),
        )


def update_job_status(job_id: int, status: str, notes: str | None = None):
    with conn() as c:
        old = c.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
        if old and old["status"] != status:
            c.execute("UPDATE jobs SET status_changed_at=? WHERE id=?", (now(), job_id))
        if notes is None:
            c.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
        else:
            c.execute("UPDATE jobs SET status=?, notes=? WHERE id=?", (status, notes, job_id))


def get_job(job_id: int):
    with conn() as c:
        r = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return _job(r) if r else None


def list_jobs(q: str = "", status: str = "", min_rel: int = 0, category: str = "",
              source: str = "", limit: int = 200):
    sql = "SELECT * FROM jobs WHERE 1=1"
    args: list = []
    if q:
        sql += " AND (title LIKE ? OR company LIKE ? OR location LIKE ?)"
        args += [f"%{q}%"] * 3
    if status:
        sql += " AND status=?"
        args.append(status)
    if min_rel:
        sql += " AND COALESCE(relevance,0) >= ?"
        args.append(min_rel)
    if category:
        sql += " AND role_category=?"
        args.append(category)
    if source:
        sql += " AND source=?"
        args.append(source)
    sql += " ORDER BY COALESCE(relevance,-1) DESC, scraped_at DESC LIMIT ?"
    args.append(limit)
    with conn() as c:
        return [_job(r) for r in c.execute(sql, args).fetchall()]


def jobs_by_ids(ids: list[int]):
    if not ids:
        return []
    with conn() as c:
        q = ",".join("?" * len(ids))
        return [_job(r) for r in c.execute(f"SELECT * FROM jobs WHERE id IN ({q})", ids).fetchall()]


def _job(r) -> dict:
    d = dict(r)
    d["tags"] = json.loads(d.get("tags") or "[]")
    d["skills"] = json.loads(d.get("skills") or "[]")
    return d


# ---------- news & riset ----------
def insert_news(run_id: int, topic: str, title: str, summary: str, url: str):
    with conn() as c:
        c.execute(
            "INSERT INTO news(run_id, topic, title, summary, url, created_at) VALUES (?,?,?,?,?,?)",
            (run_id, topic, title, summary, url, now()),
        )


def list_news(limit: int = 30):
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM news ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]


def save_research(job_id: int, company: str, content: str):
    with conn() as c:
        c.execute(
            "INSERT INTO company_research(job_id, company, content, created_at) VALUES (?,?,?,?)",
            (job_id, company, content, now()),
        )


def get_research(job_id: int):
    with conn() as c:
        r = c.execute(
            "SELECT * FROM company_research WHERE job_id=? ORDER BY id DESC LIMIT 1", (job_id,)
        ).fetchone()
        return dict(r) if r else None


def query(sql: str, args: tuple = ()):
    with conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def save_prep(job_id: int, content: str):
    with conn() as c:
        c.execute("INSERT INTO interview_prep(job_id, content, created_at) VALUES (?,?,?)",
                  (job_id, content, now()))


def get_prep(job_id: int):
    with conn() as c:
        r = c.execute("SELECT * FROM interview_prep WHERE job_id=? ORDER BY id DESC LIMIT 1",
                      (job_id,)).fetchone()
        return dict(r) if r else None
