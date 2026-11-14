# SatuBeasiswa

Portal beasiswa dengan formulir pendaftaran, kode pelacakan, pemantauan status, dan dashboard admin. Frontend ada di `public/`.

## Menjalankan versi lokal

Versi lokal memakai Python standar dan SQLite. Dari folder proyek:

```powershell
$env:BEASISWA_ADMIN_PASSWORD = 'KataSandiAdminYangKuat!'
python server.py
```

Buka `http://127.0.0.1:8000/` untuk portal dan `http://127.0.0.1:8000/admin.html` untuk admin. Server hanya mengikat ke komputer lokal.

## Deploy ke Vercel

Versi deploy memakai FastAPI di Vercel Functions dan PostgreSQL terkelola. Lihat README lengkap setelah berkas proyek diunggah. Jangan masukkan kata sandi, session secret, atau data pendaftar ke GitHub.