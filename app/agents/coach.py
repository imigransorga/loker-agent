"""Agent KAYLA — Coach: persiapan interview untuk satu loker."""
from .. import db, llm

SYSTEM = (
    "Kamu Kayla, pelatih interview kerja IT yang ramah untuk fresh graduate & junior di Indonesia. "
    "Jawab dalam Bahasa Indonesia, format markdown, praktis dan spesifik ke lowongan. "
    "Kerangka jawaban berupa poin panduan (bukan cerita karangan) agar kandidat mengisi dengan pengalaman nyatanya."
)


def candidates(limit: int = 40):
    return db.query(
        """SELECT id, title, company, status, relevance FROM jobs
           ORDER BY CASE status WHEN 'interview' THEN 0 WHEN 'dilamar' THEN 1 WHEN 'disimpan' THEN 2 ELSE 3 END,
                    COALESCE(relevance,0) DESC LIMIT ?""", (limit,))


def prepare(job_id: int) -> str:
    job = db.get_job(job_id)
    if not job:
        raise ValueError("Loker tidak ditemukan")
    content = llm.ask_text(
        SYSTEM,
        f"Lowongan: {job['title']} di {job.get('company') or '-'} ({job.get('location') or '-'})\n"
        f"Skill diminta: {', '.join(job['skills']) or '-'}\n"
        f"Deskripsi:\n{(job.get('description') or '-')[:5000]}\n\n"
        "Siapkan materi latihan interview:\n"
        "1. Ringkasan singkat posisi & apa yang kemungkinan dinilai\n"
        "2. 6 pertanyaan teknis yang mungkin muncul + poin kunci jawaban\n"
        "3. 5 pertanyaan HR/behavioral + kerangka jawaban metode STAR\n"
        "4. Perkenalan diri 60 detik (template untuk fresh grad/junior)\n"
        "5. 4 pertanyaan cerdas untuk ditanyakan balik ke interviewer\n"
        "6. Checklist H-1 (teknis, dokumen, riset perusahaan)",
    )
    db.save_prep(job_id, content)
    return content
