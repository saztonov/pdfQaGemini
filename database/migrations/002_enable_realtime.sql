-- Enable Supabase Realtime for qa_jobs and qa_messages tables
-- Run this in Supabase SQL Editor

-- Enable Realtime for qa_jobs table (for job status updates)
ALTER PUBLICATION supabase_realtime ADD TABLE public.qa_jobs;

-- Enable Realtime for qa_messages table (for new message notifications)
ALTER PUBLICATION supabase_realtime ADD TABLE public.qa_messages;

-- Verify tables are added to publication
-- SELECT * FROM pg_publication_tables WHERE pubname = 'supabase_realtime';
