-- ============================================
-- Migration 002: Create tables and fix schema for server mode
-- Run this in Supabase SQL Editor
-- ============================================

-- ========== PART 1: Create missing tables ==========

-- 1.1 Create qa_jobs table (for async LLM job processing)
CREATE TABLE IF NOT EXISTS public.qa_jobs (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL,
    client_id text NOT NULL,

    -- Job specification
    user_text text NOT NULL,
    system_prompt text DEFAULT ''::text,
    user_text_template text DEFAULT ''::text,
    model_name text NOT NULL,
    thinking_level text NOT NULL DEFAULT 'low'::text,
    thinking_budget integer,
    file_refs jsonb DEFAULT '[]'::jsonb,

    -- Job status: queued, processing, completed, failed
    status text NOT NULL DEFAULT 'queued'::text,
    progress real DEFAULT 0,

    -- Result (populated when completed)
    result_message_id uuid,
    result_text text,
    result_actions jsonb DEFAULT '[]'::jsonb,
    result_is_final boolean DEFAULT false,

    -- Error handling
    error_message text,
    retry_count integer DEFAULT 0,
    max_retries integer DEFAULT 3,

    -- Timing
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    updated_at timestamp with time zone NOT NULL DEFAULT now(),

    CONSTRAINT qa_jobs_pkey PRIMARY KEY (id)
);

COMMENT ON TABLE public.qa_jobs IS 'Tracks async LLM job processing for client-server architecture';
COMMENT ON COLUMN public.qa_jobs.status IS 'Job status: queued, processing, completed, failed';
COMMENT ON COLUMN public.qa_jobs.result_message_id IS 'FK to the assistant message created when job completes';

-- 1.2 Add foreign keys for qa_jobs (only if referenced tables exist)
DO $$
BEGIN
    -- FK to qa_conversations
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'qa_jobs_conversation_id_fkey'
    ) THEN
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'qa_conversations') THEN
            ALTER TABLE public.qa_jobs
            ADD CONSTRAINT qa_jobs_conversation_id_fkey
            FOREIGN KEY (conversation_id) REFERENCES public.qa_conversations(id) ON DELETE CASCADE;
        END IF;
    END IF;

    -- FK to qa_messages
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'qa_jobs_result_message_id_fkey'
    ) THEN
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'qa_messages') THEN
            ALTER TABLE public.qa_jobs
            ADD CONSTRAINT qa_jobs_result_message_id_fkey
            FOREIGN KEY (result_message_id) REFERENCES public.qa_messages(id) ON DELETE SET NULL;
        END IF;
    END IF;
END $$;

-- 1.3 Create indexes for qa_jobs
CREATE INDEX IF NOT EXISTS qa_jobs_status_idx ON public.qa_jobs(status);
CREATE INDEX IF NOT EXISTS qa_jobs_conversation_id_idx ON public.qa_jobs(conversation_id);
CREATE INDEX IF NOT EXISTS qa_jobs_client_id_idx ON public.qa_jobs(client_id);
CREATE INDEX IF NOT EXISTS qa_jobs_created_at_idx ON public.qa_jobs(created_at DESC);

-- ========== PART 2: Fix user_prompts table ==========

-- 2.1 Add client_id column to user_prompts table (required for server API)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_prompts') THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'user_prompts'
            AND column_name = 'client_id'
        ) THEN
            ALTER TABLE public.user_prompts
            ADD COLUMN client_id text NOT NULL DEFAULT 'default';

            COMMENT ON COLUMN public.user_prompts.client_id IS 'Client identifier for multi-tenant support';
        END IF;
    END IF;
END $$;

-- 2.2 Create index on user_prompts.client_id
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_prompts') THEN
        CREATE INDEX IF NOT EXISTS idx_user_prompts_client_id ON public.user_prompts(client_id);
    END IF;
END $$;

-- ========== PART 3: Create triggers ==========

-- 3.1 Ensure update_updated_at_column function exists
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3.2 Add trigger for qa_jobs.updated_at auto-update
DROP TRIGGER IF EXISTS qa_jobs_updated_at ON public.qa_jobs;
CREATE TRIGGER qa_jobs_updated_at
    BEFORE UPDATE ON public.qa_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 3.3 Add trigger for user_prompts.updated_at auto-update
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_prompts') THEN
        DROP TRIGGER IF EXISTS user_prompts_updated_at ON public.user_prompts;
        CREATE TRIGGER user_prompts_updated_at
            BEFORE UPDATE ON public.user_prompts
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- ========== PART 4: Enable Realtime ==========

DO $$
BEGIN
    -- Enable for qa_jobs (required for job status updates)
    BEGIN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.qa_jobs;
        RAISE NOTICE 'Added qa_jobs to realtime';
    EXCEPTION WHEN duplicate_object THEN
        RAISE NOTICE 'qa_jobs already in realtime publication';
    END;

    -- Enable for qa_messages (required for new message notifications)
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'qa_messages') THEN
            ALTER PUBLICATION supabase_realtime ADD TABLE public.qa_messages;
            RAISE NOTICE 'Added qa_messages to realtime';
        END IF;
    EXCEPTION WHEN duplicate_object THEN
        RAISE NOTICE 'qa_messages already in realtime publication';
    END;

    -- Enable for qa_conversations (optional, for multi-device sync)
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'qa_conversations') THEN
            ALTER PUBLICATION supabase_realtime ADD TABLE public.qa_conversations;
            RAISE NOTICE 'Added qa_conversations to realtime';
        END IF;
    EXCEPTION WHEN duplicate_object THEN
        RAISE NOTICE 'qa_conversations already in realtime publication';
    END;
END $$;

-- ========== PART 5: Grant permissions ==========

GRANT SELECT, INSERT, UPDATE, DELETE ON public.qa_jobs TO anon, authenticated;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'qa_messages') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.qa_messages TO anon, authenticated;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'qa_conversations') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.qa_conversations TO anon, authenticated;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_prompts') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.user_prompts TO anon, authenticated;
    END IF;
END $$;

-- ========== PART 6: Verify migration ==========

DO $$
DECLARE
    v_qa_jobs_exists boolean;
    v_client_id_exists boolean;
    v_qa_jobs_trigger_exists boolean;
BEGIN
    -- Check qa_jobs table
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'qa_jobs'
    ) INTO v_qa_jobs_exists;

    -- Check client_id column in user_prompts
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'user_prompts'
        AND column_name = 'client_id'
    ) INTO v_client_id_exists;

    -- Check qa_jobs trigger
    SELECT EXISTS (
        SELECT 1 FROM information_schema.triggers
        WHERE trigger_name = 'qa_jobs_updated_at'
    ) INTO v_qa_jobs_trigger_exists;

    RAISE NOTICE '';
    RAISE NOTICE '=== Migration 002 Verification ===';
    RAISE NOTICE 'qa_jobs table exists: %', v_qa_jobs_exists;
    RAISE NOTICE 'user_prompts.client_id exists: %', v_client_id_exists;
    RAISE NOTICE 'qa_jobs_updated_at trigger exists: %', v_qa_jobs_trigger_exists;
    RAISE NOTICE '';

    IF v_qa_jobs_exists AND v_qa_jobs_trigger_exists THEN
        RAISE NOTICE '✓ Migration 002 completed successfully!';
    ELSE
        RAISE WARNING '✗ Migration 002 may be incomplete. Please check above.';
    END IF;
END $$;
