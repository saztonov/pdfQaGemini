-- Migration: Add token_count column to qa_gemini_files
-- Run this in Supabase SQL Editor

ALTER TABLE public.qa_gemini_files
ADD COLUMN IF NOT EXISTS token_count bigint;

COMMENT ON COLUMN public.qa_gemini_files.token_count IS 'Token count calculated by tiktoken';
