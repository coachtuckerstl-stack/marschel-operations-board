import os
from typing import List, Optional
from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "")
IMPORT_TOKEN = os.getenv("IMPORT_TOKEN", "")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    job_number = Column(String, unique=True, index=True)
    job_name = Column(String)
    customer = Column(String)
    pm = Column(String)
    address = Column(String)
    city = Column(String)
    state_zip = Column(String)
    start_date = Column(String)
    date_entered = Column(String)
    duration_days = Column(String)
    laborers_needed = Column(String)
    operators_needed = Column(String)
    job_type = Column(String)
    priority = Column(String)
    status = Column(String, default="Active")
    updated_at = Column(DateTime, default=datetime.utcnow)

class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    classification = Column(String)
    phone = Column(String)
    email = Column(String)
    active = Column(String, default="Yes")

class Equipment(Base):
    __tablename__ = "equipment"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    category = Column(String)
    active = Column(String, default="Yes")

class ScheduleItem(Base):
    __tablename__ = "schedule_items"
    id = Column(Integer, primary_key=True)
    schedule_date = Column(String)
    job_number = Column(String)
    resource_type = Column(String)
    resource_name = Column(String)
    is_lead = Column(String, default="No")

class AccountingJob(BaseModel):
    job_number: Optional[str] = ""
    job_name: Optional[str] = ""
    customer: Optional[str] = ""
    pm: Optional[str] = ""
    address: Optional[str] = ""
    city: Optional[str] = ""
    state_zip: Optional[str] = ""
    ret_notes: Optional[str] = ""

class ImportPayload(BaseModel):
    jobs: List[AccountingJob]

app = FastAPI()

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

@app.get("/api/health")
def health():
    return {"ok": True, "app": "Marschel Operations Board"}

@app.get("/api/jobs")
def get_jobs():
    db = SessionLocal()
    try:
        rows = db.query(Job).order_by(Job.pm, Job.job_number).all()
        return {"ok": True, "jobs": [
            {
                "job_number": r.job_number,
                "job_name": r.job_name,
                "customer": r.customer,
                "pm": r.pm,
                "address": r.address,
                "city": r.city,
                "state_zip": r.state_zip,
                "start_date": r.start_date,
                "date_entered": r.date_entered,
                "duration_days": r.duration_days,
                "laborers_needed": r.laborers_needed,
                "operators_needed": r.operators_needed,
                "job_type": r.job_type,
                "priority": r.priority,
                "status": r.status,
            } for r in rows
        ]}
    finally:
        db.close()

@app.post("/api/import-accounting-jobs")
def import_accounting_jobs(payload: ImportPayload, x_import_token: str = Header(default="")):
    if IMPORT_TOKEN and x_import_token != IMPORT_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid import token")

    db = SessionLocal()
    imported = 0
    updated = 0
    skipped = 0

    try:
        for item in payload.jobs:
            if (item.ret_notes or "").strip().lower() == "done":
                skipped += 1
                continue

            job_number = (item.job_number or "").strip()
            job_name = (item.job_name or "").strip()

            if not job_number and not job_name:
                skipped += 1
                continue

            job = db.query(Job).filter(Job.job_number == job_number).first() if job_number else None

            if job:
                updated += 1
            else:
                job = Job(job_number=job_number)
                db.add(job)
                imported += 1

            # Accounting-owned fields only.
            job.job_name = job_name
            job.customer = (item.customer or "").strip()
            job.pm = (item.pm or "").strip()
            job.address = (item.address or "").strip()
            job.city = (item.city or "").strip()
            job.state_zip = (item.state_zip or "").strip()
            job.status = job.status or "Active"
            job.updated_at = datetime.utcnow()

        db.commit()

        return {
            "ok": True,
            "imported": imported,
            "updated": updated,
            "skipped": skipped,
        }
    finally:
        db.close()

app.mount("/", StaticFiles(directory=".", html=True), name="static")
