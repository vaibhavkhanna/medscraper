# 🏥 MedScrape — Hospital Directory Extractor

A full-stack web scraper that crawls hospital and medical clinic websites to extract doctor names, specialties, emails, and phone numbers — exported as CSV files.

---

## 🚀 Quick Start

### 1. Backend Setup

```bash
cd backend
pip install -r requirements.txt

# Install Playwright browsers (for JS-heavy sites)
playwright install chromium

# Start the API server
python main.py
# → Running at http://localhost:8000
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
# → Running at http://localhost:3000
```

### 3. CLI Usage (no UI needed)

```bash
# From the repo root:
python cli.py --url https://hospital.com
python cli.py --url hospital.com --cap 100 --output ./results.csv
```

### 4. API Usage (direct HTTP)

```bash
# Start a scrape job
curl -X POST http://localhost:8000/api/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://hospital.com", "page_cap": 150}'

# Check job status (use job_id from above response)
curl http://localhost:8000/api/jobs/{job_id}

# Download CSV when done
curl -O http://localhost:8000/api/jobs/{job_id}/download
```

---

## 📋 CSV Output Format

| Column | Description |
|--------|-------------|
| `name` | Doctor's full name (e.g. Dr. Jane Smith) |
| `specialty` | Medical specialty (e.g. Cardiology) |
| `email` | Email address if found |
| `phone` | Phone number if found |
| `source_url` | Page where the data was extracted from |
| `job_id` | Scrape job identifier |

---

## 🔧 How It Works

1. **Sitemap check** — Tries `/sitemap.xml` first for a list of all pages
2. **Smart crawling** — Follows internal links, prioritizing pages with doctor signals (URLs containing `/doctors`, `/staff`, `/team`, etc.)
3. **JS fallback** — Uses `requests + BeautifulSoup` by default; automatically falls back to `Playwright` (headless Chrome) if the page appears to be JavaScript-rendered
4. **Extraction pipeline**:
   - Finds HTML blocks that look like doctor cards (by class names, IDs)
   - Extracts names via `Dr.` / `Prof.` prefixes and credential suffixes (`MD`, `MBBS`, etc.)
   - Matches emails via RFC-compliant regex
   - Matches phone numbers with international format support
   - Detects specialties from a curated list of 60+ medical fields
5. **Deduplication** — Fingerprints by name + email + phone to prevent duplicate rows
6. **robots.txt** — Respected by default to stay compliant

---

## ⚙️ Configuration

| Setting | Default | Notes |
|---------|---------|-------|
| Page cap | 150 | Max pages per domain crawl |
| Crawl delay | 0.5s | Pause between requests (polite crawling) |
| Request timeout | 15s | Per-page fetch timeout |
| Max redirects | 5 | Per request |

---

## 🗂️ Project Structure

```
hospital-scraper/
├── backend/
│   ├── main.py          # FastAPI app + endpoints
│   ├── crawler.py       # Link discovery, sitemap, BS4/Playwright
│   ├── extractor.py     # Regex + heuristic doctor info extraction
│   ├── job_manager.py   # In-memory job queue + status tracking
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx      # Full React UI
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── cli.py               # Command-line interface
├── outputs/             # CSV files saved here
└── README.md
```

---

## ⚖️ Legal & Ethical Use

- This tool respects `robots.txt` by default
- Use only on websites where you have permission to scrape
- Do not use for spam or unsolicited contact
- Verify applicable laws in your jurisdiction before use
