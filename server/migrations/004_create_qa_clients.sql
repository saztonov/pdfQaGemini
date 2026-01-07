-- Migration: Create qa_clients table for client authentication
-- Server settings (Supabase, Gemini, R2) are in .env
-- This table stores client_id + api_token pairs

-- Create qa_clients table
CREATE TABLE IF NOT EXISTS public.qa_clients (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    client_id text NOT NULL,
    api_token uuid NOT NULL DEFAULT gen_random_uuid(),
    name text,                          -- Human-readable name
    default_model text DEFAULT 'gemini-2.0-flash',
    is_active boolean DEFAULT true,     -- Can disable access
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT qa_clients_pkey PRIMARY KEY (id),
    CONSTRAINT qa_clients_client_id_key UNIQUE (client_id),
    CONSTRAINT qa_clients_api_token_key UNIQUE (api_token)
);

-- Index for fast token lookup
CREATE INDEX IF NOT EXISTS idx_qa_clients_api_token ON public.qa_clients(api_token);
CREATE INDEX IF NOT EXISTS idx_qa_clients_client_id ON public.qa_clients(client_id);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS qa_clients_updated_at ON public.qa_clients;
CREATE TRIGGER qa_clients_updated_at
    BEFORE UPDATE ON public.qa_clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Enable Realtime (optional, for admin panel)
ALTER PUBLICATION supabase_realtime ADD TABLE public.qa_clients;
