"""Vercel-compatible API for the SatuBeasiswa portal.

Static pages are served from public/ by Vercel's CDN. The API uses a managed
PostgreSQL database (for example Neon) configured with DATABASE_URL.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import psycopg
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "database" / "postgres_schema.sql"
COOKIE_NAME = "rb_admin_session"
PBKDF2_ROUNDS = 260_000
_SCHEMA_READY = False
_SCHEMA_LOCK = threading.Lock()

app = FastAPI(title="SatuBeasiswa API", docs_url=None, redoc_url=None)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": "Data formulir belum lengkap atau formatnya tidak valid."})


class ApplicationInput(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    phone: str = Field(default="", max_length=30)
    institution: str = Field(min_length=2, max_length=160)
    degree_level: Literal["S1", "S2", "S3"]
    scholarship_id: int = Field(gt=0)
    motivation: str = Field(min_length=30, max_length=3000)


class NewsletterInput(BaseModel):
    email: str = Field(min_length=5, max_length=254)


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class DecisionInput(BaseModel):
    status: Literal["accepted", "rejected"]
    reviewer_note: str = Field(default="", max_length=1000)


def raw_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise HTTPException(status_code=503, detail="Database belum diatur. Hubungkan PostgreSQL dan isi DATABASE_URL di Vercel.")
    return psycopg.connect(database_url, connect_timeout=8, row_factory=dict_row)


def ensure_database():
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    with _SCHEMA_LOCK:
        if _SCHEMA_READY:
            return
        with raw_connection() as conn:
            schema = SCHEMA_PATH.read_text(encoding="utf-8")
            for statement in schema.split(";"):
                if statement.strip():
                    conn.execute(statement)
            conn.executemany("""INSERT INTO scholarships
                (slug, name, provider, country, location_type, degree_levels, funding_type, description, deadline, application_url, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (slug) DO NOTHING""", [
                ("lpdp-reguler", "Beasiswa Reguler LPDP", "Lembaga Pengelola Dana Pendidikan", "Indonesia", "Dalam Negeri", "S2,S3", "Fully funded", "Dukungan pendidikan magister dan doktoral di dalam maupun luar negeri.", "2026-03-31", "https://lpdp.kemenkeu.go.id/", "open"),
                ("erasmus-mundus", "Erasmus Mundus", "European Union", "Eropa", "Luar Negeri", "S2", "Fully funded", "Program master lintas negara di universitas unggulan Eropa.", "2026-01-15", "https://erasmus-plus.ec.europa.eu/", "open"),
                ("mext", "MEXT Scholarship", "Ministry of Education, Culture, Sports, Science and Technology", "Jepang", "Luar Negeri", "S1,S2,S3", "Fully funded", "Kesempatan kuliah di Jepang dengan dukungan biaya pendidikan.", "2026-04-24", "https://www.studyinjapan.go.jp/en/", "open"),
                ("beasiswa-unggulan", "Beasiswa Unggulan", "Kementerian Pendidikan, Kebudayaan, Riset, dan Teknologi", "Indonesia", "Dalam Negeri", "S1", "Prestasi", "Dukungan bagi putra-putri terbaik bangsa untuk kuliah sarjana.", None, "https://beasiswaunggulan.kemdikbud.go.id/", "upcoming"),
            ])
            admin_password = os.environ.get("ADMIN_PASSWORD")
            if admin_password:
                username = os.environ.get("ADMIN_USERNAME", "admin")
                existing = conn.execute("SELECT id FROM admin_users WHERE username=%s", (username,)).fetchone()
                if not existing:
                    salt = secrets.token_bytes(16)
                    digest = hashlib.pbkdf2_hmac("sha256", admin_password.encode(), salt, PBKDF2_ROUNDS).hex()
                    conn.execute("INSERT INTO admin_users(username,password_salt,password_hash) VALUES (%s,%s,%s)", (username, salt.hex(), digest))
        _SCHEMA_READY = True


def connection():
    ensure_database()
    return raw_connection()


def email_is_valid(value: str) -> bool:
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value.strip()))


def status_label(value: str) -> str:
    return {"submitted": "Sedang ditinjau", "accepted": "Diterima", "rejected": "Ditolak"}.get(value, value)


def issue_session(username: str) -> str:
    secret = os.environ.get("SESSION_SECRET")
    if not secret or len(secret) < 32:
        raise HTTPException(status_code=503, detail="SESSION_SECRET belum diatur dengan nilai acak minimal 32 karakter.")
    expires = int((datetime.now(timezone.utc) + timedelta(hours=8)).timestamp())
    data = f"{username}:{expires}".encode()
    encoded = base64.urlsafe_b64encode(data).rstrip(b"=").decode()
    signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def session_user(request: Request) -> str | None:
    token = request.cookies.get(COOKIE_NAME, "")
    secret = os.environ.get("SESSION_SECRET", "")
    if not token or not secret or "." not in token:
        return None
    encoded, signature = token.rsplit(".", 1)
    expected = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        username, expiry = base64.urlsafe_b64decode(padded).decode().rsplit(":", 1)
        if int(expiry) < int(datetime.now(timezone.utc).timestamp()):
            return None
        return username
    except (ValueError, UnicodeDecodeError):
        return None


def require_admin(request: Request) -> str:
    username = session_user(request)
    if not username:
        raise HTTPException(status_code=401, detail="Silakan masuk sebagai admin.")
    return username


def verify_same_origin(request: Request):
    origin = request.headers.get("origin")
    if origin and urlparse(origin).netloc != request.headers.get("host"):
        raise HTTPException(status_code=403, detail="Sumber permintaan tidak diizinkan.")


@app.get("/api/scholarships")
def scholarships():
    with connection() as conn:
        rows = conn.execute("""SELECT id,name,provider,country,location_type,degree_levels,funding_type,deadline,status
            FROM scholarships WHERE status != 'closed' ORDER BY deadline NULLS LAST""").fetchall()
    return {"scholarships": rows}


@app.post("/api/applications", status_code=201)
def create_application(data: ApplicationInput, request: Request):
    verify_same_origin(request)
    name, email = data.full_name.strip(), data.email.strip().lower()
    institution, degree = data.institution.strip(), data.degree_level.upper()
    motivation = data.motivation.strip()
    if not email_is_valid(email):
        raise HTTPException(status_code=400, detail="Alamat email tidak valid.")
    now = datetime.now(timezone.utc)
    code = "RB-" + secrets.token_hex(12).upper()
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    with connection() as conn:
        scholarship = conn.execute("SELECT id,degree_levels FROM scholarships WHERE id=%s AND status IN ('open','upcoming')", (data.scholarship_id,)).fetchone()
        if not scholarship:
            raise HTTPException(status_code=400, detail="Beasiswa tidak tersedia untuk pendaftaran saat ini.")
        allowed = {item.strip().upper() for item in scholarship["degree_levels"].split(",")}
        if degree not in allowed:
            raise HTTPException(status_code=400, detail="Jenjang yang dipilih tidak sesuai dengan beasiswa.")
        applicant = conn.execute("""INSERT INTO applicants(full_name,email,phone,institution,degree_level)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT(email) DO UPDATE SET email=EXCLUDED.email RETURNING id""",
            (name, email, data.phone.strip() or None, institution, degree)).fetchone()
        applicant_id = applicant["id"]
        if conn.execute("SELECT id FROM applications WHERE applicant_id=%s AND scholarship_id=%s", (applicant_id, data.scholarship_id)).fetchone():
            raise HTTPException(status_code=409, detail="Kamu sudah mendaftar beasiswa ini.")
        conn.execute("""INSERT INTO applications(applicant_id,scholarship_id,status,motivation,submitted_name,
            submitted_phone,submitted_institution,submitted_degree,tracking_code_hash,created_at,updated_at)
            VALUES (%s,%s,'submitted',%s,%s,%s,%s,%s,%s,%s,%s)""",
            (applicant_id, data.scholarship_id, motivation, name, data.phone.strip() or None, institution, degree, code_hash, now, now))
    return {"ok": True, "tracking_code": code, "message": "Pendaftaran berhasil dikirim."}


@app.get("/api/track")
def track(code: str, email: str):
    normalized_code, normalized_email = code.strip().upper(), email.strip().lower()
    if not normalized_code or not email_is_valid(normalized_email):
        raise HTTPException(status_code=400, detail="Masukkan kode pelacakan dan email yang valid.")
    code_hash = hashlib.sha256(normalized_code.encode()).hexdigest()
    with connection() as conn:
        row = conn.execute("""SELECT a.status,a.reviewer_note,a.created_at,a.updated_at,s.name AS scholarship_name,
            COALESCE(a.submitted_name,p.full_name) AS full_name FROM applications a
            JOIN applicants p ON p.id=a.applicant_id JOIN scholarships s ON s.id=a.scholarship_id
            WHERE a.tracking_code_hash=%s AND lower(p.email)=%s""", (code_hash, normalized_email)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Data pendaftaran tidak ditemukan. Periksa kode dan email.")
    row["status_label"] = status_label(row["status"])
    return {"application": row}


@app.post("/api/newsletter")
def subscribe(data: NewsletterInput, request: Request):
    verify_same_origin(request)
    email = data.email.strip().lower()
    if not email_is_valid(email):
        raise HTTPException(status_code=400, detail="Alamat email tidak valid.")
    with connection() as conn:
        conn.execute("INSERT INTO newsletter_subscribers(email) VALUES (%s) ON CONFLICT(email) DO UPDATE SET is_active=TRUE", (email,))
    return {"ok": True, "message": "Terima kasih sudah berlangganan."}


@app.post("/api/admin/login")
def admin_login(data: LoginInput, request: Request, response: Response):
    verify_same_origin(request)
    ensure_database()
    with raw_connection() as conn:
        row = conn.execute("SELECT password_salt,password_hash FROM admin_users WHERE username=%s", (data.username.strip(),)).fetchone()
    if not row:
        hashlib.pbkdf2_hmac("sha256", data.password.encode(), b"not-a-real-salt", PBKDF2_ROUNDS)
        raise HTTPException(status_code=401, detail="Nama pengguna atau kata sandi salah.")
    digest = hashlib.pbkdf2_hmac("sha256", data.password.encode(), bytes.fromhex(row["password_salt"]), PBKDF2_ROUNDS).hex()
    if not hmac.compare_digest(digest, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Nama pengguna atau kata sandi salah.")
    response.set_cookie(COOKIE_NAME, issue_session(data.username.strip()), max_age=8 * 60 * 60,
        httponly=True, secure=bool(os.environ.get("VERCEL")), samesite="strict", path="/")
    return {"ok": True}


@app.get("/api/admin/me")
def admin_me(request: Request):
    username = session_user(request)
    if not username:
        raise HTTPException(status_code=401, detail="Silakan masuk sebagai admin.")
    return {"authenticated": True, "username": username}


@app.post("/api/admin/logout")
def admin_logout(request: Request, response: Response):
    verify_same_origin(request)
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, secure=bool(os.environ.get("VERCEL")), samesite="strict")
    return {"ok": True}


@app.get("/api/admin/applications")
def admin_applications(request: Request):
    require_admin(request)
    with connection() as conn:
        rows = conn.execute("""SELECT a.id,a.status,a.motivation,a.reviewer_note,a.created_at,a.updated_at,a.reviewed_at,
            s.name AS scholarship_name,COALESCE(a.submitted_name,p.full_name) AS full_name,p.email,
            COALESCE(a.submitted_phone,p.phone) AS phone,COALESCE(a.submitted_institution,p.institution) AS institution,
            COALESCE(a.submitted_degree,p.degree_level) AS degree_level FROM applications a
            JOIN applicants p ON p.id=a.applicant_id JOIN scholarships s ON s.id=a.scholarship_id
            ORDER BY CASE a.status WHEN 'submitted' THEN 0 ELSE 1 END,a.created_at DESC""").fetchall()
    return {"applications": rows}


@app.patch("/api/admin/applications/{application_id}")
def decide_application(application_id: int, data: DecisionInput, request: Request):
    require_admin(request)
    verify_same_origin(request)
    now = datetime.now(timezone.utc)
    with connection() as conn:
        result = conn.execute("""UPDATE applications SET status=%s,reviewer_note=%s,reviewed_at=%s,updated_at=%s
            WHERE id=%s RETURNING id""", (data.status, data.reviewer_note.strip() or None, now, now, application_id)).fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Pendaftaran tidak ditemukan.")
    return {"ok": True, "status": data.status}

