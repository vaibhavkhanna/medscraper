"""
job_manager.py — In-memory job store that is mirrored to SQLite via SQLAlchemy.

On startup any existing jobs are reloaded from the DB so a server restart
does not lose history.
"""

import uuid
import time
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from database import SessionLocal, JobModel, JobLogModel, init_db


# ── Init DB tables on import ─────────────────────────────────────────────────
init_db()


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE    = "done"
    FAILED  = "failed"


@dataclass
class ScrapeJob:
    """In-memory job object — mirrored to the DB on every meaningful change."""
    job_id:        str
    url:           str
    page_cap:      int            = 150
    status:        JobStatus      = JobStatus.PENDING
    pages_crawled: int            = 0
    doctors_found: int            = 0
    pages_total:   int            = 0
    error:         Optional[str]  = None
    csv_path:      Optional[str]  = None
    created_at:    float          = field(default_factory=time.time)
    finished_at:   Optional[float]= None
    log:           list           = field(default_factory=list)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def add_log(self, msg: str):
        entry = {"time": time.time(), "msg": msg}
        self.log.append(entry)
        if len(self.log) > 200:
            self.log = self.log[-200:]
        # Persist log entry to DB
        _write_log(self.job_id, entry["time"], msg)

    def save(self):
        """Persist current state of this job to SQLite."""
        _upsert_job(self)


# ── DB helpers (use their own sessions so they're thread-safe) ────────────────

def _upsert_job(job: ScrapeJob):
    with SessionLocal() as db:
        row = db.get(JobModel, job.job_id)
        if row is None:
            row = JobModel(job_id=job.job_id)
            db.add(row)
        row.url           = job.url
        row.page_cap      = job.page_cap
        row.status        = job.status
        row.pages_crawled = job.pages_crawled
        row.pages_total   = job.pages_total
        row.doctors_found = job.doctors_found
        row.error         = job.error
        row.csv_path      = job.csv_path
        row.created_at    = job.created_at
        row.finished_at   = job.finished_at
        db.commit()


def _write_log(job_id: str, timestamp: float, message: str):
    with SessionLocal() as db:
        db.add(JobLogModel(job_id=job_id, timestamp=timestamp, message=message))
        db.commit()


def _load_jobs_from_db() -> dict:
    """Re-hydrate in-memory job store from SQLite on startup."""
    jobs = {}
    with SessionLocal() as db:
        rows = db.query(JobModel).all()
        for row in rows:
            logs = [
                {"time": lg.timestamp, "msg": lg.message}
                for lg in db.query(JobLogModel)
                           .filter(JobLogModel.job_id == row.job_id)
                           .order_by(JobLogModel.timestamp)
                           .all()
            ]
            job = ScrapeJob(
                job_id        = row.job_id,
                url           = row.url,
                page_cap      = row.page_cap,
                status        = JobStatus(row.status) if row.status in JobStatus._value2member_map_ else JobStatus.FAILED,
                pages_crawled = row.pages_crawled,
                doctors_found = row.doctors_found,
                pages_total   = row.pages_total,
                error         = row.error,
                csv_path      = row.csv_path,
                created_at    = row.created_at,
                finished_at   = row.finished_at,
                log           = logs[-200:],
            )
            # Jobs that were RUNNING when the server died → mark as FAILED
            if job.status == JobStatus.RUNNING:
                job.status = JobStatus.FAILED
                job.error  = "Server restarted while job was running"
                _upsert_job(job)
            jobs[job.job_id] = job
    return jobs


# ── Manager ───────────────────────────────────────────────────────────────────

class JobManager:
    def __init__(self):
        self._jobs: dict[str, ScrapeJob] = _load_jobs_from_db()

    def create_job(self, url: str, page_cap: int = 150) -> ScrapeJob:
        job_id = str(uuid.uuid4())[:8]
        job = ScrapeJob(job_id=job_id, url=url, page_cap=page_cap)
        self._jobs[job_id] = job
        job.save()  # persist immediately
        return job

    def get_job(self, job_id: str) -> Optional[ScrapeJob]:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[ScrapeJob]:
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def delete_job(self, job_id: str):
        self._jobs.pop(job_id, None)
        with SessionLocal() as db:
            row = db.get(JobModel, job_id)
            if row:
                db.delete(row)
                db.commit()


job_manager = JobManager()
