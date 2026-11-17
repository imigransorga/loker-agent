"""Kantor AI Loker — dashboard 5 agent."""
import json
import threading

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db, llm
from .agents import analyst, coach, info, scout
from .config import BASE_DIR, CLAUDE_MODEL, DEFAULT_LEVELS, DEFAULT_LOCATIONS, ROLE_CATEGORIES, claude_enabled

app = FastAPI(title="Kantor AI Loker")
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")
templates.env.filters["fromjson"] = json.loads

AGENTS = [
    {"key": "scout", "name": "Kia", "title": "Scout", "role": "Scout · Pencari Loker", "icon": "🔎", "ready": True,
     "desc": "Kumpulkan loker IT terbaru (QA, FE, BE, web dev, SE) untuk fresh grad & junior, nilai kecocokannya, dan cari berita pasar kerja."},
    {"key": "applier", "name": "Nuri", "title": "Applier", "role": "Applier · Pencocok & Pelamar", "icon": "📨", "ready": False,
     "desc": "Upload 1 CV → dicocokkan ke tiap loker, dibuatkan CV & cover letter khusus, lalu dibantu melamar (semi-otomatis)."},
    {"key": "builder", "name": "Dian", "title": "Builder", "role": "Builder · CV & Portofolio", "icon": "🧾", "ready": False,
     "desc": "Satu prompt → CV ATS-friendly, halaman portofolio, compro, ringkasan LinkedIn."},
    {"key": "info", "name": "Dimas", "title": "Pusat Info", "role": "Pusat Info · Brief Harian", "icon": "📬", "ready": True,
     "desc": "Brief harian: loker baru, lamaran yang perlu di-follow-up, jadwal interview, dan berita terbaru."},
    {"key": "analyst", "name": "Sabrina", "title": "Analyst", "role": "Analyst · Analis Data", "icon": "📊", "ready": True,
     "desc": "Statistik loker yang di-scrape, funnel lamaran, skill paling dicari, dan saran mingguan."},
    {"key": "coach", "name": "Kayla", "title": "Coach", "role": "Coach · Pelatih Interview", "icon": "🎤", "ready": True,
     "desc": "Pilih satu loker → disiapkan pertanyaan interview teknis & HR beserta kerangka jawaban, pertanyaan balik, dan checklist."},
    {"key": "manager", "name": "Putri", "title": "Manager", "role": "Manager · Koordinator", "icon": "🧑‍💼", "ready": False,
     "desc": "Beri 1 perintah, Putri membagi tugas ke karyawan lain."},
]


# Tampilan karakter 3D tiap agent
LOOKS_3D = {
    "scout":   {"shirt": "#2f6fed", "hair": "#2b1d16", "skin": "#f1c7a4", "hair_style": "short", "extra": "headset"},
    "applier": {"shirt": "#e0773b", "hair": "#3b2a4a", "skin": "#d9a27c", "hair_style": "hijab", "extra": ""},
    "builder": {"shirt": "#8a5cf6", "hair": "#5a3825", "skin": "#f3d1b5", "hair_style": "long", "extra": ""},
    "analyst": {"shirt": "#1f9d74", "hair": "#1d1d1d", "skin": "#c98d62", "hair_style": "curly", "extra": "glasses"},
    "manager": {"shirt": "#3c4658", "hair": "#444444", "skin": "#e8b896", "hair_style": "cap", "extra": ""},
    "coach":   {"shirt": "#e85d9a", "hair": "#3a2418", "skin": "#e9bf99", "hair_style": "bun", "extra": "glasses"},
    "info":    {"shirt": "#f2b134", "hair": "#6b3e26", "skin": "#d8a07a", "hair_style": "long", "extra": "headset"},
}


@app.on_event("startup")
def _startup():
    db.init_db()


def _ctx(request: Request, **kw):
    return {"request": request, "claude": claude_enabled(), "model": CLAUDE_MODEL,
            "nav_agents": AGENTS, "nav_looks": LOOKS_3D, **kw}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    s = analyst.stats()
    runs = db.list_runs("scout", 1)
    last_run = runs[0] if runs else None
    if last_run:
        last_run["stats"] = json.loads(last_run["stats"] or "{}")
    scout_running = bool(last_run and last_run["status"] == "running")
    agents3d = [{
        "key": a["key"], "name": a["name"], "role": a["role"], "icon": a["icon"],
        "state": "busy" if (a["key"] == "scout" and scout_running) else ("work" if a["ready"] else "off"),
        "look": LOOKS_3D[a["key"]],
    } for a in AGENTS]
    board = {k: s[k] for k in ("total", "high", "applied", "interview")}
    return templates.TemplateResponse(request, "home.html", _ctx(
        request, agents=AGENTS, s=s, top_jobs=db.list_jobs(limit=6), last_run=last_run,
        news=db.list_news(3), agents3d=agents3d, board=board,
        brief=info.brief(), coach_jobs=coach.candidates()))


# ---------------- Scout ----------------
@app.get("/scout", response_class=HTMLResponse)
def scout_page(request: Request, q: str = "", status: str = "", min_rel: int = 0,
               category: str = "", source: str = ""):
    jobs = db.list_jobs(q, status, min_rel, category, source)
    sources_list = [r["source"] for r in db.query("SELECT DISTINCT source FROM jobs ORDER BY source")]
    return templates.TemplateResponse(request, "scout.html", _ctx(
        request, jobs=jobs, runs=db.list_runs("scout", 8), news=db.list_news(12),
        f={"q": q, "status": status, "min_rel": min_rel, "category": category, "source": source},
        statuses=db.JOB_STATUSES, categories=list(ROLE_CATEGORIES) + ["Lainnya"],
        sources_list=sources_list,
        default_roles="QA, tester, frontend, backend, fullstack, web developer, software engineer, programmer, mobile developer",
        default_levels=", ".join(DEFAULT_LEVELS), default_locations=", ".join(DEFAULT_LOCATIONS),
    ))


@app.post("/api/scout/run")
async def scout_run(request: Request):
    if request.headers.get("content-type", "").startswith("application/json"):
        payload = await request.json()
    else:
        form = await request.form()
        payload = {k: (form.getlist(k) if k == "sources" else form.get(k)) for k in form.keys()}
        payload.setdefault("news", "false")
    payload = scout.normalize_payload(payload)
    running = [r for r in db.list_runs("scout", 5) if r["status"] == "running"]
    if running:
        raise HTTPException(409, "Scout masih bekerja, tunggu sampai selesai")
    run_id = db.create_run("scout", payload)
    threading.Thread(target=scout.run, args=(run_id, payload), daemon=True).start()
    return {"run_id": run_id, "payload": payload}


@app.get("/api/runs/{run_id}")
def run_status(run_id: int):
    r = db.get_run(run_id)
    if not r:
        raise HTTPException(404)
    return r


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, job_id: int):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "job.html", _ctx(
        request, job=job, research=db.get_research(job_id), statuses=db.JOB_STATUSES))


@app.post("/jobs/{job_id}/status")
async def job_status(request: Request, job_id: int):
    form = await request.form()
    status = form.get("status", "")
    if status not in db.JOB_STATUSES:
        raise HTTPException(400, "status tidak valid")
    db.update_job_status(job_id, status, form.get("notes"))
    return RedirectResponse(request.headers.get("referer") or f"/jobs/{job_id}", status_code=303)


@app.post("/api/jobs/{job_id}/research")
def job_research(job_id: int):
    try:
        return {"content": scout.research_company(job_id)}
    except (llm.ClaudeError, ValueError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)


# ---------------- Analyst ----------------
@app.get("/analyst", response_class=HTMLResponse)
def analyst_page(request: Request):
    return templates.TemplateResponse(request, "analyst.html", _ctx(request, s=analyst.stats()))


@app.get("/api/analyst/stats")
def analyst_stats():
    return analyst.stats()


@app.post("/api/analyst/insight")
def analyst_insight():
    try:
        return {"content": analyst.insight()}
    except llm.ClaudeError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


# ---------- Kayla (coach) ----------
@app.post("/api/coach/{job_id}")
def coach_prepare(job_id: int):
    try:
        return {"content": coach.prepare(job_id)}
    except (llm.ClaudeError, ValueError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.get("/api/coach/{job_id}")
def coach_get(job_id: int):
    p = db.get_prep(job_id)
    return p or JSONResponse({"error": "belum ada"}, status_code=404)


@app.get("/agent/{key}", response_class=HTMLResponse)
def agent_soon(request: Request, key: str):
    a = next((a for a in AGENTS if a["key"] == key), None)
    if not a:
        raise HTTPException(404)
    if a["ready"]:
        return RedirectResponse(f"/{key}" if key in ("scout", "analyst") else f"/?agent={key}")
    return templates.TemplateResponse(request, "soon.html", _ctx(request, a=a))
