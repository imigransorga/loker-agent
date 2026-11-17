"""Konfigurasi & profil pencari kerja (target posisi, level, lokasi)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "data" / "loker.db"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")

# Posisi yang dicari (dipakai filter judul & prompt Claude)
DEFAULT_ROLES = [
    "QA", "quality assurance", "tester", "software engineer", "software developer",
    "web developer", "frontend", "front-end", "front end", "backend", "back-end",
    "back end", "fullstack", "full-stack", "full stack", "programmer",
    "mobile developer", "android", "flutter", "react", "laravel", "php", "node",
    "python developer", "golang", "devops", "data analyst", "it support",
]

# Level target
DEFAULT_LEVELS = ["fresh graduate", "junior", "entry level", "intern"]

# Kata di judul yang menandakan loker terlalu senior -> dibuang
SENIOR_WORDS = [
    "senior", "sr.", "sr ", "lead", "principal", "staff", "head of", "manager",
    "director", "architect", "vp ", "chief", "expert", "10+ years", "8+ years",
]

DEFAULT_LOCATIONS = ["Indonesia", "Jakarta", "Bandung", "Remote"]

# Kategori posisi untuk statistik
ROLE_CATEGORIES = {
    "QA / Tester": ["qa", "quality assurance", "tester", "test engineer", "sdet"],
    "Frontend": ["frontend", "front-end", "front end", "react", "vue", "angular", "ui developer"],
    "Backend": ["backend", "back-end", "back end", "laravel", "php", "golang", "node", "java developer", "python developer"],
    "Fullstack": ["fullstack", "full-stack", "full stack"],
    "Mobile": ["mobile", "android", "ios", "flutter", "react native", "kotlin"],
    "Web Developer": ["web developer", "web programmer", "wordpress"],
    "DevOps / Cloud": ["devops", "cloud", "sre", "infrastructure"],
    "Data": ["data analyst", "data engineer", "data scientist", "machine learning"],
    "Software Engineer": ["software engineer", "software developer", "programmer", "developer", "engineer"],
}

# Kamus skill untuk statistik "skill paling dicari" (dipakai bila Claude tidak aktif)
SKILL_KEYWORDS = [
    "JavaScript", "TypeScript", "React", "Vue", "Angular", "Next.js", "Node.js",
    "PHP", "Laravel", "Python", "Django", "FastAPI", "Java", "Spring", "Go", "Golang",
    "Kotlin", "Swift", "Flutter", "Dart", "C#", ".NET", "Ruby", "SQL", "MySQL",
    "PostgreSQL", "MongoDB", "Redis", "Docker", "Kubernetes", "AWS", "GCP", "Azure",
    "Git", "REST", "GraphQL", "Selenium", "Cypress", "Playwright", "Jest", "Postman",
    "Tailwind", "HTML", "CSS", "Linux", "CI/CD", "Figma",
]


def claude_enabled() -> bool:
    return bool(ANTHROPIC_API_KEY)
