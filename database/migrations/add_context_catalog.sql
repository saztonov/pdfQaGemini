-- Add context_catalog column to qa_jobs table
-- Run this migration in Supabase SQL Editor

-- Add column for storing context_catalog JSON
ALTER TABLE public.qa_jobs
ADD COLUMN IF NOT EXISTS context_catalog text DEFAULT '';

COMMENT ON COLUMN public.qa_jobs.context_catalog IS 'JSON string with available context items (crops) for agentic requests';
