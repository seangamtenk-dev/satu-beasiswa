INSERT OR IGNORE INTO scholarships
  (slug, name, provider, country, location_type, degree_levels, funding_type, description, deadline, application_url, status)
VALUES
  ('lpdp-reguler', 'Beasiswa Reguler LPDP', 'Lembaga Pengelola Dana Pendidikan', 'Indonesia', 'Dalam Negeri', 'S2,S3', 'Fully funded', 'Dukungan penuh untuk studi magister dan doktoral di dalam maupun luar negeri.', '2026-03-31', 'https://lpdp.kemenkeu.go.id/', 'open'),
  ('erasmus-mundus', 'Erasmus Mundus', 'European Union', 'Eropa', 'Luar Negeri', 'S2', 'Fully funded', 'Belajar lintas negara di program master unggulan universitas Eropa.', '2026-01-15', 'https://erasmus-plus.ec.europa.eu/', 'open'),
  ('mext', 'MEXT Scholarship', 'Ministry of Education, Culture, Sports, Science and Technology', 'Jepang', 'Luar Negeri', 'S1,S2,S3', 'Fully funded', 'Kesempatan kuliah di Jepang dengan dukungan biaya dan pengalaman budaya.', '2026-04-24', 'https://www.studyinjapan.go.jp/en/', 'open'),
  ('beasiswa-unggulan', 'Beasiswa Unggulan', 'Kementerian Pendidikan, Kebudayaan, Riset, dan Teknologi', 'Indonesia', 'Dalam Negeri', 'S1', 'Prestasi', 'Apresiasi bagi putra-putri terbaik bangsa untuk pendidikan sarjana.', NULL, 'https://beasiswaunggulan.kemdikbud.go.id/', 'upcoming');

