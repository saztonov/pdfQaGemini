-- Enable Supabase Realtime for job tracking
-- Run this in Supabase SQL Editor after creating qa_jobs table

-- Enable Realtime for qa_jobs (required for job status updates)
ALTER PUBLICATION supabase_realtime ADD TABLE public.qa_jobs;

-- Enable Realtime for qa_messages (required for new message notifications)
ALTER PUBLICATION supabase_realtime ADD TABLE public.qa_messages;

-- Optional: Enable Realtime for qa_conversations (for multi-device sync)
ALTER PUBLICATION supabase_realtime ADD TABLE public.qa_conversations;
