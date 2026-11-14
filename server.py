#!/usr/bin/env python3
"""Development server and SQLite API for the SatuBeasiswa demo."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "database" / "ruangbeasiswa.sqlite"
HOST = os.environ.get("BEASISWA_HOST", "127.0.0.1")
PORT = int(os.environ.get("BEASISWA_PORT", "8000"))
ADMIN_USER = os.environ.get("BEASISWA_ADMIN_USER", "admin")
DEMO_PASSWORD = "PortalBeasiswa2026!"
SESSIONS: dict[str, float] = {}
COOKIE_NAME = "rb_admin_session"
PBKDF2_ROUNDS = 260_000


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def init_database() -> None:
    with connect() as db:
        db.executescript((ROOT / "database" / "schema.sql").read_text(encoding="utf-8"))
        applicant_columns = {r[1] for r in db.execute("PRAGMA table_info(applicants)")}
        if "institution" not in applicant_columns:
            db.execute("ALTER TABLE applicants ADD COLUMN institution TEXT")
        application_columns = {r[1] for r in db.execute("PRAGMA table_info(applications)")}
        migrations = {
            "motivation": "TEXT",
            "submitted_name": "TEXT",
            "submitted_phone": "TEXT",
            "submitted_institution": "TEXT",
            "submitted_degree": "TEXT",
            "tracking_code_hash": "TEXT",
            "reviewer_note": "TEXT",
            "reviewed_at": "DATETIME",
        }
        for column, data_type in migrations.items():
            if column not in application_columns:
                db.execute(f"ALTER TABLE applications ADD COLUMN {column} {data_type}")
        db.executescript((ROOT / "database" / "seed.sql").read_text(encoding="utf-8"))
        admin = db.execute("SELECT id FROM admin_users WHERE username = ?", (ADMIN_USER,)).fetchone()
        if not admin:
            salt = secrets.token_bytes(16)
            password = os.environ.get("BEASISWA_ADMIN_PASSWORD", DEMO_PASSWORD)
            digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
            db.execute(
                "INSERT INTO admin_users(username, password_salt, password_hash) VALUES (?, ?, ?)",
                (ADMIN_USER, salt.hex(), digest.hex()),
            )


def password_matches(username: str, password: str) -> bool:
    with connect() as db:
        row = db.execute("SELECT password_salt, password_hash FROM admin_users WHERE username = ?", (username,)).fetchone()
    if not row:
        # Spend comparable time for unknown usernames to reduce timing leaks.
        hashlib.pbkdf2_hmac("sha256", password.encode(), b"not-a-real-salt", PBKDF2_ROUNDS)
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(row["password_salt"]), PBKDF2_ROUNDS).hex()
    return hmac.compare_digest(digest, row["password_hash"])


def status_label(status: str) -> str:
    return {"submitted": "Sedang ditinjau", "accepted": "Diterima", "rejected": "Ditolak"}.get(status, status)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "public"), **kwargs)

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def json_response(self, payload, status=HTTPStatus.OK, headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Ukuran permintaan tidak valid.")
        if length < 1 or length > 24_000:
            raise ValueError("Data formulir kosong atau terlalu besar.")
        if "application/json" not in self.headers.get("Content-Type", ""):
            raise ValueError("Format data tidak didukung.")
        try:
            value = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ValueError("Data formulir tidak valid.")
        if not isinstance(value, dict):
            raise ValueError("Data formulir tidak valid.")
        return value

    def origin_is_local(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True
        parsed = urlparse(origin)
        return parsed.netloc == self.headers.get("Host")

    def session_token(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            return cookie[COOKIE_NAME].value if COOKIE_NAME in cookie else None
        except Exception:
            return None

    def authenticated(self):
        token = self.session_token()
        expiry = SESSIONS.get(token) if token else None
        if expiry and expiry > time.time():
            return True
        if token:
            SESSIONS.pop(token, None)
        return False

    def require_admin(self):
        if self.authenticated():
            return True
        self.json_response({"error": "Silakan masuk sebagai admin."}, HTTPStatus.UNAUTHORIZED)
        return False

    def do_GET(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            return super().do_GET()
        if parsed.path == "/api/scholarships":
            with connect() as db:
                rows = db.execute("SELECT id, name, provider, country, location_type, degree_levels, funding_type, deadline, status FROM scholarships WHERE status != 'closed' ORDER BY deadline IS NULL, deadline").fetchall()
            return self.json_response({"scholarships": [dict(row) for row in rows]})
        if parsed.path == "/api/track":
            values = parse_qs(parsed.query)
            code = values.get("code", [""])[0].strip().upper()
            email = values.get("email", [""])[0].strip().lower()
            if not code or not email:
                return self.json_response({"error": "Masukkan kode pelacakan dan email."}, HTTPStatus.BAD_REQUEST)
            code_hash = hashlib.sha256(code.encode()).hexdigest()
            with connect() as db:
                row = db.execute("""SELECT a.status, a.reviewer_note, a.created_at, a.updated_at,
                    s.name AS scholarship_name, COALESCE(a.submitted_name, p.full_name) AS full_name
                    FROM applications a JOIN applicants p ON p.id=a.applicant_id
                    JOIN scholarships s ON s.id=a.scholarship_id
                    WHERE a.tracking_code_hash=? AND lower(p.email)=?""", (code_hash, email)).fetchone()
            if not row:
                return self.json_response({"error": "Data pendaftaran tidak ditemukan. Periksa kembali kode dan email."}, HTTPStatus.NOT_FOUND)
            return self.json_response({"application": {**dict(row), "status_label": status_label(row["status"])}})
        if parsed.path == "/api/admin/me":
            if not self.authenticated():
                return self.json_response({"authenticated": False}, HTTPStatus.UNAUTHORIZED)
            return self.json_response({"authenticated": True, "username": ADMIN_USER})
        if parsed.path == "/api/admin/applications":
            if not self.require_admin():
                return
            with connect() as db:
                rows = db.execute("""SELECT a.id, a.status, a.motivation, a.reviewer_note, a.created_at, a.updated_at,
                    a.reviewed_at, s.name AS scholarship_name,
                    COALESCE(a.submitted_name, p.full_name) AS full_name, p.email,
                    COALESCE(a.submitted_phone, p.phone) AS phone,
                    COALESCE(a.submitted_institution, p.institution) AS institution,
                    COALESCE(a.submitted_degree, p.degree_level) AS degree_level
                    FROM applications a JOIN applicants p ON p.id=a.applicant_id
                    JOIN scholarships s ON s.id=a.scholarship_id
                    ORDER BY CASE a.status WHEN 'submitted' THEN 0 WHEN 'saved' THEN 1 ELSE 2 END, a.created_at DESC""").fetchall()
            return self.json_response({"applications": [dict(row) for row in rows]})
        return self.json_response({"error": "Endpoint tidak ditemukan."}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            return self.send_error(HTTPStatus.NOT_FOUND)
        if not self.origin_is_local():
            return self.json_response({"error": "Sumber permintaan tidak diizinkan."}, HTTPStatus.FORBIDDEN)
        try:
            data = self.read_json()
        except ValueError as exc:
            return self.json_response({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        if parsed.path == "/api/admin/login":
            username = str(data.get("username", ""))[:120]
            password = str(data.get("password", ""))[:256]
            if not password_matches(username, password):
                return self.json_response({"error": "Nama pengguna atau kata sandi salah."}, HTTPStatus.UNAUTHORIZED)
            token = secrets.token_urlsafe(32)
            SESSIONS[token] = time.time() + 8 * 60 * 60
            return self.json_response({"ok": True}, headers={"Set-Cookie": f"{COOKIE_NAME}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800"})
        if parsed.path == "/api/admin/logout":
            token = self.session_token()
            if token:
                SESSIONS.pop(token, None)
            return self.json_response({"ok": True}, headers={"Set-Cookie": f"{COOKIE_NAME}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"})
        if parsed.path == "/api/applications":
            return self.create_application(data)
        if parsed.path == "/api/newsletter":
            email = str(data.get("email", "")).strip().lower()
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
                return self.json_response({"error": "Alamat email tidak valid."}, HTTPStatus.BAD_REQUEST)
            with connect() as db:
                db.execute("INSERT INTO newsletter_subscribers(email) VALUES (?) ON CONFLICT(email) DO UPDATE SET is_active=1", (email,))
            return self.json_response({"ok": True, "message": "Terima kasih sudah berlangganan."})
        return self.json_response({"error": "Endpoint tidak ditemukan."}, HTTPStatus.NOT_FOUND)

    def create_application(self, data):
        name = str(data.get("full_name", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        phone = str(data.get("phone", "")).strip()
        institution = str(data.get("institution", "")).strip()
        degree = str(data.get("degree_level", "")).strip().upper()
        motivation = str(data.get("motivation", "")).strip()
        try:
            scholarship_id = int(data.get("scholarship_id", 0))
        except (ValueError, TypeError):
            scholarship_id = 0
        if not (2 <= len(name) <= 120 and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email or "") and len(email) <= 254):
            return self.json_response({"error": "Nama atau alamat email belum valid."}, HTTPStatus.BAD_REQUEST)
        if len(phone) > 30 or not (2 <= len(institution) <= 160) or degree not in {"S1", "S2", "S3"}:
            return self.json_response({"error": "Lengkapi institusi, jenjang, dan nomor telepon yang valid."}, HTTPStatus.BAD_REQUEST)
        if not 30 <= len(motivation) <= 3000:
            return self.json_response({"error": "Motivasi harus berisi 30 sampai 3.000 karakter."}, HTTPStatus.BAD_REQUEST)
        code = "RB-" + secrets.token_hex(5).upper()
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        with connect() as db:
            scholarship = db.execute("SELECT id, degree_levels FROM scholarships WHERE id=? AND status IN ('open', 'upcoming')", (scholarship_id,)).fetchone()
            if not scholarship:
                return self.json_response({"error": "Beasiswa tidak tersedia untuk pendaftaran saat ini."}, HTTPStatus.BAD_REQUEST)
            allowed_degrees = {x.strip().upper() for x in scholarship["degree_levels"].split(",")}
            if degree not in allowed_degrees:
                return self.json_response({"error": "Jenjang yang dipilih tidak sesuai dengan beasiswa."}, HTTPStatus.BAD_REQUEST)
            existing = db.execute("SELECT id FROM applicants WHERE lower(email)=?", (email,)).fetchone()
            if existing:
                applicant_id = existing["id"]
            else:
                cur = db.execute("INSERT INTO applicants(full_name,email,phone,institution,degree_level) VALUES(?,?,?,?,?)", (name, email, phone or None, institution, degree))
                applicant_id = cur.lastrowid
            duplicate = db.execute("SELECT id FROM applications WHERE applicant_id=? AND scholarship_id=?", (applicant_id, scholarship_id)).fetchone()
            if duplicate:
                return self.json_response({"error": "Kamu sudah mendaftar beasiswa ini."}, HTTPStatus.CONFLICT)
            try:
                db.execute("""INSERT INTO applications(applicant_id, scholarship_id, status, motivation,
                    submitted_name, submitted_phone, submitted_institution, submitted_degree,
                    tracking_code_hash, created_at, updated_at)
                    VALUES(?,?,'submitted',?,?,?,?,?,?,?,?)""",
                    (applicant_id, scholarship_id, motivation, name, phone or None, institution, degree, code_hash, now, now))
            except sqlite3.IntegrityError:
                return self.json_response({"error": "Pendaftaran tidak dapat disimpan. Periksa kembali data yang dimasukkan."}, HTTPStatus.CONFLICT)
        return self.json_response({"ok": True, "tracking_code": code, "message": "Pendaftaran berhasil dikirim."}, HTTPStatus.CREATED)

    def do_PATCH(self):
        parsed = urlparse(self.path)
        match = re.fullmatch(r"/api/admin/applications/(\d+)", parsed.path)
        if not match:
            return self.json_response({"error": "Endpoint tidak ditemukan."}, HTTPStatus.NOT_FOUND)
        if not self.origin_is_local():
            return self.json_response({"error": "Sumber permintaan tidak diizinkan."}, HTTPStatus.FORBIDDEN)
        if not self.require_admin():
            return
        try:
            data = self.read_json()
        except ValueError as exc:
            return self.json_response({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        status = str(data.get("status", ""))
        note = str(data.get("reviewer_note", "")).strip()
        if status not in {"accepted", "rejected"} or len(note) > 1000:
            return self.json_response({"error": "Status atau catatan admin tidak valid."}, HTTPStatus.BAD_REQUEST)
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        with connect() as db:
            cur = db.execute("UPDATE applications SET status=?, reviewer_note=?, reviewed_at=?, updated_at=? WHERE id=?", (status, note or None, now, now, int(match.group(1))))
            if cur.rowcount == 0:
                return self.json_response({"error": "Pendaftaran tidak ditemukan."}, HTTPStatus.NOT_FOUND)
        return self.json_response({"ok": True, "status": status})


def main():
    init_database()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"SatuBeasiswa berjalan di http://{HOST}:{PORT}")
    print(f"Dashboard admin: http://{HOST}:{PORT}/admin.html")
    server.serve_forever()


if __name__ == "__main__":
    main()

