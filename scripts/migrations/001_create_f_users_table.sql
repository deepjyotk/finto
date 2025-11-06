-- Create f_users table for authentication
-- This table stores user credentials and basic profile information

CREATE TABLE IF NOT EXISTS f_users (
    user_id UUID PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_f_users_username ON f_users(username);
CREATE INDEX IF NOT EXISTS idx_f_users_email ON f_users(email);

-- Create a trigger to automatically update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_f_users_updated_at ON f_users;
CREATE TRIGGER update_f_users_updated_at
    BEFORE UPDATE ON f_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security (RLS) for security
ALTER TABLE f_users ENABLE ROW LEVEL SECURITY;

-- Create policy: Users can read their own data
DROP POLICY IF EXISTS "Users can view own data" ON f_users;
CREATE POLICY "Users can view own data"
    ON f_users FOR SELECT
    USING (auth.uid()::text = user_id::text);

-- Create policy: Users can update their own data
DROP POLICY IF EXISTS "Users can update own data" ON f_users;
CREATE POLICY "Users can update own data"
    ON f_users FOR UPDATE
    USING (auth.uid()::text = user_id::text);

-- Note: INSERT policy is handled by service role (backend creates users)
