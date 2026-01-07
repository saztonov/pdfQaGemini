-- Recreate qa_clients table

-- Drop existing table
DROP TABLE IF EXISTS public.qa_clients CASCADE;

-- Create table
CREATE TABLE public.qa_clients (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    client_id text NOT NULL,
    api_token uuid NOT NULL DEFAULT gen_random_uuid(),
    name text,
    default_model text DEFAULT 'gemini-3-flash-preview'::text,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT qa_clients_pkey PRIMARY KEY (id),
    CONSTRAINT qa_clients_client_id_key UNIQUE (client_id),
    CONSTRAINT qa_clients_api_token_key UNIQUE (api_token)
);

-- Indexes
CREATE INDEX idx_qa_clients_api_token ON public.qa_clients USING btree (api_token);
CREATE INDEX idx_qa_clients_client_id ON public.qa_clients USING btree (client_id);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS qa_clients_updated_at ON public.qa_clients;
CREATE TRIGGER qa_clients_updated_at
    BEFORE UPDATE ON public.qa_clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert default client
INSERT INTO public.qa_clients (client_id, name, default_model)
VALUES ('default', 'Default Client', 'gemini-3-flash-preview')
RETURNING client_id, api_token;
