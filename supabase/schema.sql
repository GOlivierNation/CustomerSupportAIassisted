-- Run this in Supabase Dashboard: SQL Editor > New query
-- Creates tables for users, sessions, tickets, channels, and channel_messages

-- Users (email + hashed password)
CREATE TABLE IF NOT EXISTS users (
  email TEXT PRIMARY KEY,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Sessions (session_id -> customer_email, optional expiry)
CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  customer_email TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '7 days')
);

CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);

-- Tickets
CREATE TABLE IF NOT EXISTS tickets (
  id TEXT PRIMARY KEY,
  subject TEXT NOT NULL,
  description TEXT NOT NULL,
  customer_email TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved')),
  ai_response TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tickets_customer_email ON tickets(customer_email);
CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at DESC);

-- Channels (chat)
CREATE TABLE IF NOT EXISTS channels (
  id TEXT PRIMARY KEY,
  customer_email TEXT NOT NULL,
  subject TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_channels_updated_at ON channels(updated_at DESC);

-- Channel messages
CREATE TABLE IF NOT EXISTS channel_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel_id TEXT NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_channel_messages_channel_id ON channel_messages(channel_id);

-- Enable Row Level Security (RLS) if you want to restrict access later.
-- For now the app uses the anon key and server-side checks, so RLS is optional.
-- ALTER TABLE users ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE channels ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE channel_messages ENABLE ROW LEVEL SECURITY;

-- If RLS is enabled and registration fails with permission errors, run these policies
-- so the anon key can insert/select (app does server-side auth checks):
--
-- CREATE POLICY "Allow anon insert users" ON users FOR INSERT TO anon WITH CHECK (true);
-- CREATE POLICY "Allow anon select users by email" ON users FOR SELECT TO anon USING (true);
-- CREATE POLICY "Allow anon insert sessions" ON sessions FOR INSERT TO anon WITH CHECK (true);
-- CREATE POLICY "Allow anon select sessions" ON sessions FOR SELECT TO anon USING (true);
-- CREATE POLICY "Allow anon delete sessions" ON sessions FOR DELETE TO anon USING (true);
