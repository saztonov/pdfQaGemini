-- Migration: 003_model_traces.sql
-- Description: Create qa_model_traces table for storing Model Inspector history

-- Table: public.qa_model_traces
-- Stores model call traces for the Model Inspector
CREATE TABLE IF NOT EXISTS public.qa_model_traces (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    ts timestamp with time zone NOT NULL DEFAULT now(),
    conversation_id uuid NOT NULL,
    client_id text NOT NULL DEFAULT 'default',
    model text NOT NULL,
    thinking_level text NOT NULL DEFAULT 'low',
    system_prompt text DEFAULT '',
    user_text text NOT NULL,
    input_files jsonb DEFAULT '[]'::jsonb,
    response_json jsonb,
    parsed_actions jsonb DEFAULT '[]'::jsonb,
    latency_ms real,
    errors jsonb DEFAULT '[]'::jsonb,
    is_final boolean DEFAULT false,
    assistant_text text DEFAULT '',
    full_thoughts text DEFAULT '',
    input_tokens integer,
    output_tokens integer,
    total_tokens integer,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT qa_model_traces_pkey PRIMARY KEY (id),
    CONSTRAINT qa_model_traces_conversation_id_fkey FOREIGN KEY (conversation_id)
        REFERENCES public.qa_conversations(id) ON DELETE CASCADE
);

-- Index for efficient queries by conversation
CREATE INDEX IF NOT EXISTS qa_model_traces_conversation_id_idx
    ON public.qa_model_traces(conversation_id);

-- Index for client_id queries
CREATE INDEX IF NOT EXISTS qa_model_traces_client_id_idx
    ON public.qa_model_traces(client_id);

-- Index for timestamp ordering (most recent first)
CREATE INDEX IF NOT EXISTS qa_model_traces_ts_idx
    ON public.qa_model_traces(ts DESC);

COMMENT ON TABLE public.qa_model_traces IS 'Stores model call traces for the Model Inspector';
COMMENT ON COLUMN public.qa_model_traces.ts IS 'Timestamp when the request was initiated';
COMMENT ON COLUMN public.qa_model_traces.input_files IS 'Array of file refs: [{name, uri, mime_type, display_name}]';
COMMENT ON COLUMN public.qa_model_traces.response_json IS 'Raw JSON response from model';
COMMENT ON COLUMN public.qa_model_traces.parsed_actions IS 'Parsed actions from model response';
COMMENT ON COLUMN public.qa_model_traces.errors IS 'Array of error messages if any';
