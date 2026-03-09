## MedScraper

MedScraper is a small end‑to‑end tool that crawls hospital and clinic websites to extract publicly available provider (doctor/staff) contact details into CSV files, with a simple web UI for managing jobs.

It is designed to run **locally on your own machine**, using only publicly available data and respecting each site’s `robots.txt` rules.

---

### Features

- **Web UI** to start new scrape jobs and see progress.
- **Doctor statistics** per job and inline results table preview.
- **CSV export** for each job.
- **JSON‑LD + HTML parsing** for better extraction quality.
- **SQLite backend** to store jobs and extracted doctors.
- **Ethics & safety**:
  - Respects `robots.txt` (including `Crawl-delay`).
  - SSRF protection: blocks non‑public IP targets.
  - Optional API key guard.
  - CORS tightened to localhost by default.

---

### Architecture

- **Backend** (`backend/`)
  - FastAPI app (`main.py`)
  - Async crawler (`crawler.py`) using `httpx`, `BeautifulSoup`, and Playwright fallback.
  - Extractors (`extractor.py`, `jsonld_parser.py`)
  - SQLite database via SQLAlchemy (`database.py`)
- **Frontend** (`frontend/`)
  - React + Vite single‑page app (`src/App.jsx`)
  - Talks to backend under `/api/*`

---

### Prerequisites

- **Python**: 3.10 or newer (3.11+ recommended)
- **Node.js**: 18+ (with `npm`)
- **OS**: macOS / Linux / Windows

Playwright is optional but recommended for JS‑heavy sites (installed automatically when you install its Python package).

---

### Setup & Run (Developer / Local Use)

From the project root:

#### 1. Backend

```bash
cd backend

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt

uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

This starts the API at `http://127.0.0.1:8000`.

#### 2. Frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Vite will print a URL like `http://localhost:5173`. Open it in a browser to use MedScraper.

---

### Optional: API Key Protection

By default, API key protection is **disabled** (for simple local use).

To enable it:

1. Set the environment variable **before** starting the backend:

```bash
export MEDSCRAPER_API_KEY="your-secret-key"
uvicorn main:app --host 127.0.0.1 --port 8000
```

2. All API clients (including the frontend) must then send:

```http
X-API-Key: your-secret-key
```

If `MEDSCRAPER_API_KEY` is unset or empty, the guard is effectively disabled and no header is required.

---

### Data Storage & Cleanup

- All runtime data lives under the `outputs/` folder:
  - `outputs/scraper.db` – SQLite database with jobs, doctors, logs.
  - `outputs/*.csv` – exported CSVs per job.
- To **wipe all jobs and doctors** (e.g. before pushing to GitLab):

```bash
rm -rf outputs
mkdir outputs
```

This removes all scraped data and starts you from a clean state.

---

### Security & Ethics

MedScraper is intended for ethical, compliant use:

- **Public data only**: it fetches pages that are publicly accessible over HTTP/HTTPS.
- **robots.txt aware**:
  - Fetches and parses `robots.txt` per domain.
  - Only crawls URLs allowed for the `HospitalScraper` user‑agent (or `*` as a fallback).
  - Respects `Crawl-delay` when present.
- **SSRF protection**:
  - Scrape URLs are normalized and resolved via DNS.
  - Targets that resolve to private, loopback, or link‑local IPs (e.g. `10.x`, `192.168.x`, `127.0.0.1`) are rejected.
- **CORS tightening**:
  - Browser access is restricted to localhost origins by default, configurable via `MEDSCRAPER_CORS_ORIGINS`.
- **Error handling**:
  - Client‑visible job errors are generic; detailed exceptions are kept in logs on the server.

If you deploy this anywhere beyond your own machine or team, you should:

- Enable `MEDSCRAPER_API_KEY` and send `X-API-Key` from any client.
- Consider additional auth (e.g. reverse‑proxy auth) and rate limiting.
- Run the crawler/Playwright in a sandboxed container/VM with limited network egress.

---

### Git & Ignore Rules

Before committing/pushing, make sure your `.gitignore` (in the repo root) excludes:

```gitignore
__pycache__/
*.pyc
.venv/
env/

frontend/node_modules/
frontend/.vite/

outputs/
*.csv
scraper.db

.DS_Store
.idea/
.vscode/
```

This keeps scraped data, build artifacts, and local environments out of version control.

---

### License / Disclaimer

MedScraper is provided as‑is for educational and internal tooling purposes.  
You are responsible for ensuring that your use complies with applicable laws, site terms of service, and data protection regulations in your jurisdiction.

