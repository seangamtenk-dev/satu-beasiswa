PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS scholarships (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  provider TEXT NOT NULL,
  country TEXT NOT NULL,
  location_type TEXT NOT NULL CHECK (location_type IN ('Dalam Negeri', 'Luar Negeri')),
  degree_levels TEXT NOT NULL,
  funding_type TEXT NOT NULL,
  description TEXT NOT NULL,
  deadline DATE,
  application_url TEXT,
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'upcoming', 'closed')),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_scholarships_status_deadline ON scholarships(status, deadline);
CREATE INDEX IF NOT EXISTS idx_scholarships_country ON scholarships(country);

CREATE TABLE IF NOT EXISTS applicants (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  full_name TEXT NOT NULL,
  email TEXT NOT NULL,
  phone TEXT,
  institution TEXT,
  degree_level TEXT,
  field_of_study TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(email)
);

CREATE TABLE IF NOT EXISTS applications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  applicant_id INTEGER NOT NULL REFERENCES applicants(id) ON DELETE CASCADE,
  scholarship_id INTEGER NOT NULL REFERENCES scholarships(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'saved' CHECK (status IN ('saved', 'preparing', 'submitted', 'accepted', 'rejected')),
  motivation TEXT,
  submitted_name TEXT,
  submitted_phone TEXT,
  submitted_institution TEXT,
  submitted_degree TEXT,
  tracking_code_hash TEXT UNIQUE,
  reviewer_note TEXT,
  reviewed_at DATETIME,
  notes TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(applicant_id, scholarship_id)
);

CREATE TABLE IF NOT EXISTS newsletter_subscribers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
  subscribed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admin_users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  password_salt TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

