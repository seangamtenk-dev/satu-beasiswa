CREATE TABLE IF NOT EXISTS scholarships (
  id BIGSERIAL PRIMARY KEY,
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
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_scholarships_status_deadline ON scholarships(status, deadline);
CREATE INDEX IF NOT EXISTS idx_scholarships_country ON scholarships(country);

CREATE TABLE IF NOT EXISTS applicants (
  id BIGSERIAL PRIMARY KEY,
  full_name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  phone TEXT,
  institution TEXT,
  degree_level TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS applications (
  id BIGSERIAL PRIMARY KEY,
  applicant_id BIGINT NOT NULL REFERENCES applicants(id) ON DELETE CASCADE,
  scholarship_id BIGINT NOT NULL REFERENCES scholarships(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'submitted' CHECK (status IN ('saved', 'preparing', 'submitted', 'accepted', 'rejected')),
  motivation TEXT,
  submitted_name TEXT,
  submitted_phone TEXT,
  submitted_institution TEXT,
  submitted_degree TEXT,
  tracking_code_hash TEXT UNIQUE,
  reviewer_note TEXT,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(applicant_id, scholarship_id)
);

CREATE TABLE IF NOT EXISTS newsletter_subscribers (
  id BIGSERIAL PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  subscribed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admin_users (
  id BIGSERIAL PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  password_salt TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

