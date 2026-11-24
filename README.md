# SatuBeasiswa

Portal beasiswa dengan formulir pendaftaran, kode pelacakan, pemantauan status, dan dashboard admin. Frontend ada di `public/`.
 
## Menyiapkan GitHub + Vercel

Versi deploy memakai FastAPI di Vercel Functions dan PostgreSQL terkelola. Vercel mendeteksi aplikasi FastAPI dari `app.py`; aset statis disajikan dari `public/`. Lihat [panduan FastAPI Vercel](https://vercel.com/docs/frameworks/backend/fastapi).

1. Buat repositori **privat** di GitHub, lalu masukkan isi folder proyek ini ke akar repositori.
2. Pastikan `database/ruangbeasiswa.sqlite` tidak diunggah. `.gitignore` mengabaikan file database lokal.
3. Di Vercel, impor repositori GitHub itu. Deploy akan berjalan lagi setiap kali kamu mengirim perubahan ke GitHub.
4. Tambahkan PostgreSQL melalui Vercel Marketplace, misalnya integrasi Neon. Pastikan variabel koneksi bernama `DATABASE_URL`; lihat [integrasi database Vercel](https://vercel.com/docs/marketplace-storage).
5. Tambahkan Environment Variables berikut di pengaturan proyek Vercel untuk Production (dan Preview jika diperlukan):
   - `DATABASE_URL` — biasanya diisi otomatis oleh integrasi database.
   - `ADMIN_USERNAME` — nama pengguna admin, misalnya `admin`.
   - `ADMIN_PASSWORD` — kata sandi admin yang kuat. Saat aplikasi pertama kali menginisialisasi database, kata sandi ini disimpan sebagai hash PBKDF2.
   - `SESSION_SECRET` — rahasia acak minimal 32 karakter. Buat dengan `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
6. Deploy ulang. Skema PostgreSQL dan data beasiswa contoh akan dibuat saat API pertama kali dipanggil. Masuk ke dashboard melalui `/admin.html`.

Vercel Hobby gratis ditujukan untuk proyek pribadi nonkomersial; periksa [ketentuan paket Hobby](https://vercel.com/docs/plans/hobby) jika portal digunakan oleh organisasi atau untuk kegiatan komersial. Marketplace dapat memiliki ketentuan dan biaya tersendiri. Jangan memasukkan kata sandi, session secret, atau data pendaftar ke GitHub.

## Catatan operasional

- `app.py` adalah backend Vercel dengan PostgreSQL. `server.py` adalah server lokal dengan SQLite.
- Skema Vercel ada di `database/postgres_schema.sql`; skema lokal ada di `database/schema.sql`.
- Isi beasiswa merupakan data contoh. Perbarui program dan tenggat dari penyedia resmi sebelum menerima pendaftaran sungguhan.
- Sebelum penggunaan publik, tambahkan pembatasan percobaan login, kebijakan privasi, pencadangan database, dan prosedur untuk menghapus data pribadi.

