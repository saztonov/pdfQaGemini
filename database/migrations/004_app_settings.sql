-- Migration: 004_app_settings
-- Description: Centralized application settings stored in Supabase
-- All configuration (except Supabase credentials) is stored here

-- Table: public.qa_app_settings
-- Description: Global application settings (key-value store)
CREATE TABLE IF NOT EXISTS public.qa_app_settings (
    key text NOT NULL,
    value text,
    value_type text NOT NULL DEFAULT 'string',  -- string, int, bool, json
    description text,
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT qa_app_settings_pkey PRIMARY KEY (key)
);

COMMENT ON TABLE public.qa_app_settings IS 'Global application settings (credentials, defaults, etc.)';
COMMENT ON COLUMN public.qa_app_settings.key IS 'Setting key (e.g., gemini_api_key, max_history_pairs)';
COMMENT ON COLUMN public.qa_app_settings.value IS 'Setting value as text (convert based on value_type)';
COMMENT ON COLUMN public.qa_app_settings.value_type IS 'Type hint: string, int, bool, json';

-- Insert default settings
INSERT INTO public.qa_app_settings (key, value, value_type, description) VALUES
    -- Gemini API
    ('gemini_api_key', '', 'string', 'Google Gemini API key'),
    ('default_model', 'gemini-3-flash-preview', 'string', 'Default model for new conversations'),

    -- R2 Storage
    ('r2_account_id', '', 'string', 'Cloudflare R2 account ID'),
    ('r2_access_key_id', '', 'string', 'R2 access key ID'),
    ('r2_secret_access_key', '', 'string', 'R2 secret access key'),
    ('r2_bucket_name', '', 'string', 'R2 bucket name'),
    ('r2_public_url', '', 'string', 'R2 public URL base'),

    -- Chat settings
    ('max_history_pairs', '5', 'int', 'Number of Q&A pairs to include in context (0 = no history)'),

    -- Worker settings
    ('worker_max_jobs', '10', 'int', 'Maximum concurrent worker jobs'),
    ('worker_job_timeout', '300', 'int', 'Job timeout in seconds'),
    ('worker_max_retries', '3', 'int', 'Maximum job retries')
ON CONFLICT (key) DO NOTHING;

-- RLS disabled (as per project convention)
ALTER TABLE public.qa_app_settings DISABLE ROW LEVEL SECURITY;

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_qa_app_settings_key ON public.qa_app_settings(key);

-- Function to get setting value with type conversion
CREATE OR REPLACE FUNCTION get_app_setting(setting_key text, default_value text DEFAULT NULL)
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
    result text;
BEGIN
    SELECT value INTO result FROM public.qa_app_settings WHERE key = setting_key;
    RETURN COALESCE(result, default_value);
END;
$$;

-- Function to set setting value
CREATE OR REPLACE FUNCTION set_app_setting(setting_key text, setting_value text)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE public.qa_app_settings
    SET value = setting_value, updated_at = now()
    WHERE key = setting_key;
END;
$$;
