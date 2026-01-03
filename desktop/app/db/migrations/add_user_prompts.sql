-- Migration: Add user_prompts table
-- Created: 2026-01-03

-- Table for storing user custom prompts
CREATE TABLE IF NOT EXISTS public.user_prompts (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    client_id text NOT NULL DEFAULT 'default'::text,
    title text NOT NULL,
    system_prompt text NOT NULL DEFAULT ''::text,
    user_text text NOT NULL DEFAULT ''::text,
    r2_key text,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT user_prompts_pkey PRIMARY KEY (id)
);

-- Index for faster queries by client_id
CREATE INDEX IF NOT EXISTS idx_user_prompts_client_id ON public.user_prompts(client_id);

-- Comments
COMMENT ON TABLE public.user_prompts IS 'User custom prompts for AI conversations';
COMMENT ON COLUMN public.user_prompts.id IS 'Unique prompt identifier';
COMMENT ON COLUMN public.user_prompts.client_id IS 'Client identifier';
COMMENT ON COLUMN public.user_prompts.title IS 'Prompt title';
COMMENT ON COLUMN public.user_prompts.system_prompt IS 'System prompt text';
COMMENT ON COLUMN public.user_prompts.user_text IS 'User prompt text';
COMMENT ON COLUMN public.user_prompts.r2_key IS 'R2 storage key for full content';
