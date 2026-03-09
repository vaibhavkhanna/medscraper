import csv
import os
import threading
import socket
import ipaddress
from urllib.parse import urlparse
import requests as req_lib
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from job_manager import job_manager, JobStatus
from crawler import crawl
from extractor import extract_from_page, ExtractedDoctor
from database import get_db, DoctorModel, init_db

# ── Config ─────────────────────────────────────────────────────────────────────
OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

DEFAULT_PAGE_CAP = 150

# Allowed browser origins for CORS. You can override this by setting the
# MEDSCRAPER_CORS_ORIGINS environment variable to a comma-separated list.
_raw_cors = os.getenv("MEDSCRAPER_CORS_ORIGINS")
if _raw_cors:
    ALLOWED_ORIGINS = [o.strip() for o in _raw_cors.split(",") if o.strip()]
else:
    ALLOWED_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

CSV_FIELDS = [
    "first_name", "last_name", "title", "contact_type",
    "specialty", "email1", "email2",
    "phone1", "phone2",
    "npi", "linkedin", "source_url", "job_id",
]

# ── App ────────────────────────────────────────────────────────────────────────
init_db()
app = FastAPI(title="Hospital Scraper API", version="3.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,  # no cookies/auth headers needed from browser
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ────────────────────────────────────────────────────────────────────
class ScrapeRequest(BaseModel):
    url: str
    page_cap: Optional[int] = DEFAULT_PAGE_CAP


class JobResponse(BaseModel):
    job_id: str
    url: str
    status: str
    pages_crawled: int
    doctors_found: int
    pages_total: int
    error: Optional[str]
    csv_ready: bool
    log: list


class DoctorResponse(BaseModel):
    id: int
    job_id: str
    first_name: str
    last_name: str
    title: str
    contact_type: str
    specialty: str
    email1: str
    email2: str
    phone1: str
    phone2: str
    npi: str
    linkedin: str
    source_url: str

    class Config:
        from_attributes = True


# ── URL / SSRF safeguards ──────────────────────────────────────────────────────

def _validate_public_http_url(raw_url: str) -> str:
    """
    Normalize and validate a scrape target URL.

    - Ensures http/https scheme and hostname are present.
    - Resolves DNS and rejects private, loopback, or link-local IPs
      to avoid SSRF into internal networks.
    """
    url = raw_url.strip()
    if not url:
        raise HTTPException(400, "URL is required")

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(400, "URL must start with http(s) and include a hostname")

    hostname = parsed.hostname

    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise HTTPException(400, "URL hostname could not be resolved")

    for _, _, _, _, sockaddr in infos:
        ip = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip)
        except ValueError:
            # Non-IP result; skip
            continue

        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
            raise HTTPException(
                400,
                "Target URL resolves to a non-public IP address, which is not allowed.",
            )

    return url


# ── Simple API key auth (optional) ─────────────────────────────────────────────

API_KEY = os.getenv("MEDSCRAPER_API_KEY") or ""


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """
    Lightweight API key guard.

    - If MEDSCRAPER_API_KEY is unset/empty: auth is effectively disabled
      (convenient for local single-user usage).
    - If set: all protected routes require an X-API-Key header matching it.
    """
    if not API_KEY:
        # Auth disabled; allow all
        return
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ── NPPES NPI Registry Lookup ──────────────────────────────────────────────────
NPPES_API = "https://npiregistry.cms.hhs.gov/api/"

def lookup_npi(first_name: str, last_name: str, specialty: str = "") -> str:
    if not first_name and not last_name:
        return ""
    try:
        params = {
            "version": "2.1",
            "first_name": first_name,
            "last_name": last_name,
            "limit": 5,
            "enumeration_type": "NPI-1",
        }
        if specialty:
            params["taxonomy_description"] = specialty

        r = req_lib.get(NPPES_API, params=params, timeout=8)
        r.raise_for_status()
        data = r.json()

        results = data.get("results", [])
        if not results and specialty:
            params.pop("taxonomy_description", None)
            r = req_lib.get(NPPES_API, params=params, timeout=8)
            results = r.json().get("results", [])

        if results:
            return str(results[0].get("number", ""))
    except Exception:
        pass
    return ""


# ── Background scrape worker ───────────────────────────────────────────────────
def run_scrape_job(job_id: str):
    from database import SessionLocal

    job = job_manager.get_job(job_id)
    if not job:
        return

    job.status = JobStatus.RUNNING
    job.save()
    job.add_log(f"Starting crawl of {job.url} (cap: {job.page_cap} pages)")

    csv_path = OUTPUTS_DIR / f"{job_id}.csv"
    seen_fingerprints: set[str] = set()
    seen_names: set[str] = set()
    doctors_written = 0

    try:
        with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
            writer.writeheader()

            def on_progress(crawled: int, queued: int):
                job.pages_crawled = crawled
                job.pages_total = crawled + queued
                job.save()

            for url, html in crawl(
                job.url,
                page_cap=job.page_cap,
                progress_callback=on_progress,
            ):
                job.add_log(f"Crawled: {url}")
                doctors = extract_from_page(html, url)

                new_count = 0
                with SessionLocal() as db:
                    for doc in doctors:
                        fp = doc.fingerprint()
                        name_fp = doc.name_fingerprint()
                        if fp in seen_fingerprints or (name_fp and name_fp in seen_names):
                            continue
                        seen_fingerprints.add(fp)
                        if name_fp:
                            seen_names.add(name_fp)

                        npi = doc.npi
                        if not npi and doc.contact_type == "Doctor":
                            job.add_log(f"  → NPI lookup: {doc.full_name}")
                            npi = lookup_npi(doc.first_name, doc.last_name, doc.specialty)
                            if npi:
                                job.add_log(f"    NPI found: {npi}")

                        row = {
                            "first_name":   doc.first_name,
                            "last_name":    doc.last_name,
                            "title":        doc.title,
                            "contact_type": doc.contact_type,
                            "specialty":    doc.specialty,
                            "email1":       doc.email1,
                            "email2":       doc.email2,
                            "phone1":       doc.phone1,
                            "phone2":       doc.phone2,
                            "npi":          npi,
                            "linkedin":     doc.linkedin,
                            "source_url":   doc.source_url,
                            "job_id":       job_id,
                        }
                        writer.writerow(row)
                        csvfile.flush()

                        # ── Persist doctor to DB ──────────────────────────
                        db.add(DoctorModel(
                            job_id       = job_id,
                            first_name   = doc.first_name,
                            last_name    = doc.last_name,
                            title        = doc.title,
                            contact_type = doc.contact_type,
                            specialty    = doc.specialty,
                            email1       = doc.email1,
                            email2       = doc.email2,
                            phone1       = doc.phone1,
                            phone2       = doc.phone2,
                            npi          = npi,
                            linkedin     = doc.linkedin,
                            source_url   = doc.source_url,
                        ))

                        new_count += 1
                        doctors_written += 1

                    db.commit()

                if new_count:
                    job.add_log(f"  → Found {new_count} provider(s) on this page")

                job.doctors_found = doctors_written
                job.save()

        job.status = JobStatus.DONE
        job.csv_path = str(csv_path)
        job.add_log(f"Done. {doctors_written} unique providers extracted.")

    except Exception as e:
        job.status = JobStatus.FAILED
        # Store only a generic message for clients; log full error internally.
        job.error = "Scrape failed due to an internal error."
        job.add_log(f"ERROR: {e}")

    import time
    job.finished_at = time.time()
    job.save()


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.post("/api/scrape", response_model=JobResponse, dependencies=[Depends(require_api_key)])
def start_scrape(req: ScrapeRequest):
    # Normalize and validate URL to avoid SSRF into private/internal networks
    url = _validate_public_http_url(req.url)

    page_cap = max(1, min(req.page_cap or DEFAULT_PAGE_CAP, 500))
    job = job_manager.create_job(url, page_cap)

    thread = threading.Thread(target=run_scrape_job, args=(job.job_id,), daemon=True)
    thread.start()

    return _job_to_response(job)


@app.get("/api/jobs/{job_id}", response_model=JobResponse, dependencies=[Depends(require_api_key)])
def get_job(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_to_response(job)


@app.get("/api/jobs", response_model=list[JobResponse], dependencies=[Depends(require_api_key)])
def list_jobs():
    return [_job_to_response(j) for j in job_manager.list_jobs()]


@app.get("/api/jobs/{job_id}/doctors", response_model=list[DoctorResponse], dependencies=[Depends(require_api_key)])
def get_job_doctors(job_id: str, db: Session = Depends(get_db)):
    """Return all extracted doctors for a given job from the database."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return db.query(DoctorModel).filter(DoctorModel.job_id == job_id).all()


@app.get("/api/doctors", response_model=list[DoctorResponse], dependencies=[Depends(require_api_key)])
def search_doctors(
    name: Optional[str] = None,
    specialty: Optional[str] = None,
    contact_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Search all doctors across all jobs with optional filters."""
    q = db.query(DoctorModel)
    if name:
        like = f"%{name}%"
        q = q.filter(
            (DoctorModel.first_name.ilike(like)) | (DoctorModel.last_name.ilike(like))
        )
    if specialty:
        q = q.filter(DoctorModel.specialty.ilike(f"%{specialty}%"))
    if contact_type:
        q = q.filter(DoctorModel.contact_type == contact_type)
    return q.limit(500).all()


@app.get("/api/jobs/{job_id}/download", dependencies=[Depends(require_api_key)])
def download_csv(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if not job.csv_path or not Path(job.csv_path).exists():
        raise HTTPException(404, "CSV not ready yet")
    return FileResponse(
        job.csv_path,
        media_type="text/csv",
        filename=f"providers_{job_id}.csv",
    )


@app.delete("/api/jobs/{job_id}", dependencies=[Depends(require_api_key)])
def delete_job(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.csv_path and Path(job.csv_path).exists():
        os.remove(job.csv_path)
    job_manager.delete_job(job_id)  # removes from memory + DB (cascade deletes doctors/logs)
    return {"deleted": True}


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ── Helpers ────────────────────────────────────────────────────────────────────
def _job_to_response(job) -> JobResponse:
    return JobResponse(
        job_id=job.job_id,
        url=job.url,
        status=job.status,
        pages_crawled=job.pages_crawled,
        doctors_found=job.doctors_found,
        pages_total=job.pages_total,
        error=job.error,
        csv_ready=job.csv_path is not None and Path(job.csv_path).exists(),
        log=job.log[-50:],
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
