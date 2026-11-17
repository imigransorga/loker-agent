# 🏢 Kantor AI Loker

Dashboard berisi 5 "karyawan" AI untuk mencari kerja IT (fresh graduate & junior).

| Agent | Status | Tugas |
|---|---|---|
| 🔎 Scout | ✅ Fase 1 | Cari loker (API publik + web search Claude ke portal Indonesia), buang duplikat & senior, nilai kecocokan, berita pasar kerja, riset perusahaan |
| 📊 Analyst | ✅ Fase 1 | Statistik loker, skill paling dicari, funnel lamaran, insight AI |
| 🧾 Builder | Fase 2 | CV/portofolio/compro dari 1 prompt |
| 📨 Applier | Fase 3 | Cocokkan CV ke loker + cover letter + lamaran semi-otomatis |
| 🧑‍💼 Manager | Fase 3 | Membagi perintah ke agent lain |

## Menjalankan

```bash
cd ~/Documents/loker-agent
# 1. isi ANTHROPIC_API_KEY di file .env
./run.sh
# 2. buka http://127.0.0.1:8800
```

Tanpa API key tetap jalan, tetapi hanya sumber API publik (Remotive, RemoteOK, Arbeitnow) dengan penilaian skor sederhana.

## Scout otomatis tiap pagi (opsional)

```bash
crontab -e
# jam 07.00 setiap hari
0 7 * * * cd ~/Documents/loker-agent && .venv/bin/python scout_cli.py >> data/cron.log 2>&1
```

## Payload Scout (API)

```bash
curl -X POST http://127.0.0.1:8800/api/scout/run -H 'content-type: application/json' -d '{
  "roles": ["QA", "frontend", "backend", "web developer"],
  "levels": ["fresh graduate", "junior"],
  "locations": ["Bandung", "Jakarta", "Remote"],
  "sources": ["web_id", "remotive", "remoteok"],
  "web_limit": 15, "ai_score_limit": 40, "news": true
}'
```

## Catatan
- Data tersimpan di `data/loker.db` (SQLite).
- RemoteOK mewajibkan sumber & link balik ditampilkan; dashboard sudah melakukannya.
- Portal Indonesia (Glints, Kalibrr, JobStreet, dll) tidak di-scrape langsung (melanggar aturan pakai & rawan diblokir). Yang dipakai web search Claude.
- Claude memakai fallback server-side (`fallbacks: "default"`): bila model menolak permintaan, otomatis diulang di model cadangan.
