"""
database.py — SQLAlchemy setup + ORM models for the hospital scraper.

Tables:
  - jobs      : one row per scrape job
  - doctors   : one row per extracted provider
  - job_logs  : append-only log messages per job
"""

import time
from pathlib import Path
from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Text, Boolean, ForeignKey
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# ── DB location ───────────────────────────────────────────────────────────────
DB_DIR = Path(__file__).parent.parent / "outputs"
DB_DIR.mkdir(exist_ok=True)
DATABASE_URL = f"sqlite:///{DB_DIR / 'scraper.db'}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite + threading
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


# ── Models ────────────────────────────────────────────────────────────────────

class JobModel(Base):
    __tablename__ = "jobs"

    job_id        = Column(String,  primary_key=True, index=True)
    url           = Column(String,  nullable=False)
    page_cap      = Column(Integer, default=150)
    status        = Column(String,  default="pending")   # pending/running/done/failed
    pages_crawled = Column(Integer, default=0)
    pages_total   = Column(Integer, default=0)
    doctors_found = Column(Integer, default=0)
    error         = Column(Text,    nullable=True)
    csv_path      = Column(String,  nullable=True)
    created_at    = Column(Float,   default=time.time)
    finished_at   = Column(Float,   nullable=True)

    doctors = relationship("DoctorModel", back_populates="job", cascade="all, delete-orphan")
    logs    = relationship("JobLogModel", back_populates="job", cascade="all, delete-orphan",
                           order_by="JobLogModel.timestamp")


class DoctorModel(Base):
    __tablename__ = "doctors"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    job_id       = Column(String,  ForeignKey("jobs.job_id", ondelete="CASCADE"), index=True)
    first_name   = Column(String,  default="")
    last_name    = Column(String,  default="")
    title        = Column(String,  default="")
    contact_type = Column(String,  default="")
    specialty    = Column(String,  default="")
    email1       = Column(String,  default="")
    email2       = Column(String,  default="")
    phone1       = Column(String,  default="")
    phone2       = Column(String,  default="")
    npi          = Column(String,  default="")
    linkedin     = Column(String,  default="")
    source_url   = Column(String,  default="")

    job = relationship("JobModel", back_populates="doctors")


class JobLogModel(Base):
    __tablename__ = "job_logs"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    job_id    = Column(String,  ForeignKey("jobs.job_id", ondelete="CASCADE"), index=True)
    timestamp = Column(Float,   default=time.time)
    message   = Column(Text,    nullable=False)

    job = relationship("JobModel", back_populates="logs")


# ── Init ──────────────────────────────────────────────────────────────────────

def init_db():
    """Create all tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
