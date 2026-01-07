-- Migration: Add api_token to qa_settings for client authentication
-- This allows clients to authenticate with a simple token instead of storing all credentials

-- Add api_token column if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'qa_settings'
        AND column_name = 'api_token'
    ) THEN
        ALTER TABLE public.qa_settings ADD COLUMN api_token uuid DEFAULT gen_random_uuid();
    END IF;
END $$;

-- Make api_token unique
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'public'
        AND tablename = 'qa_settings'
        AND indexname = 'qa_settings_api_token_key'
    ) THEN
        ALTER TABLE public.qa_settings ADD CONSTRAINT qa_settings_api_token_key UNIQUE (api_token);
    END IF;
END $$;

-- Create index for fast token lookup
CREATE INDEX IF NOT EXISTS idx_qa_settings_api_token ON public.qa_settings(api_token);

-- Ensure existing rows have tokens (if any null)
UPDATE public.qa_settings SET api_token = gen_random_uuid() WHERE api_token IS NULL;

-- Make api_token NOT NULL after ensuring all rows have values
-- (commented out for safety - run manually after verification)
-- ALTER TABLE public.qa_settings ALTER COLUMN api_token SET NOT NULL;
