# Database RuangBeasiswa

Database menggunakan SQLite, sehingga tidak perlu memasang atau menjalankan server database terpisah.

- `ruangbeasiswa.sqlite` — database siap digunakan.
- `schema.sql` — definisi tabel dan indeks.
- `seed.sql` — data beasiswa contoh.

Tabel yang tersedia: `scholarships`, `applicants`, `applications`, dan `newsletter_subscribers`. Data tenggat pada seed adalah contoh awal dan perlu diperbarui sesuai pengumuman resmi penyedia beasiswa.

Untuk membuat ulang database dengan Python:

```bash
python -c "import sqlite3,pathlib; p=pathlib.Path('ruangbeasiswa.sqlite'); c=sqlite3.connect(p); c.executescript(pathlib.Path('schema.sql').read_text(encoding='utf-8')); c.executescript(pathlib.Path('seed.sql').read_text(encoding='utf-8')); c.close()"
```

