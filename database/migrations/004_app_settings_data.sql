-- Script to populate qa_app_settings with actual values
-- Run this after 004_app_settings.sql migration
--
-- IMPORTANT: Sensitive values (API keys, secrets) should be set via the
-- desktop Settings dialog or API, NOT directly in SQL. They will be encrypted
-- automatically by the server using AES-256-GCM.
--
-- This script only sets NON-SENSITIVE values.

-- =====================================================
-- NON-SENSITIVE SETTINGS (safe to set directly in SQL)
-- =====================================================

-- Default model
UPDATE public.qa_app_settings SET value = 'gemini-2.0-flash' WHERE key = 'default_model';

-- R2 non-secret settings
UPDATE public.qa_app_settings SET value = '<YOUR_R2_ACCOUNT_ID>' WHERE key = 'r2_account_id';
UPDATE public.qa_app_settings SET value = '<YOUR_R2_BUCKET_NAME>' WHERE key = 'r2_bucket_name';
UPDATE public.qa_app_settings SET value = '<YOUR_R2_PUBLIC_URL>' WHERE key = 'r2_public_url';

-- Chat settings (history context)
UPDATE public.qa_app_settings SET value = '5' WHERE key = 'max_history_pairs';

-- Worker settings
UPDATE public.qa_app_settings SET value = '10' WHERE key = 'worker_max_jobs';
UPDATE public.qa_app_settings SET value = '300' WHERE key = 'worker_job_timeout';
UPDATE public.qa_app_settings SET value = '3' WHERE key = 'worker_max_retries';

-- =====================================================
-- SENSITIVE SETTINGS - DO NOT SET HERE!
-- =====================================================
-- The following keys must be set via Settings dialog or API:
--   - gemini_api_key
--   - r2_access_key_id
--   - r2_secret_access_key
--
-- These values will be encrypted server-side before storage.
-- Direct SQL inserts will NOT be encrypted and will fail decryption.

-- =====================================================
-- Verify settings (shows masked sensitive values)
-- =====================================================
SELECT key,
       CASE
           WHEN key IN ('gemini_api_key', 'r2_access_key_id', 'r2_secret_access_key')
           THEN CASE
               WHEN value IS NULL OR value = '' THEN '(not set)'
               WHEN value LIKE 'enc:v1:%' THEN '(encrypted)'
               ELSE '(WARNING: not encrypted!)'
           END
           ELSE COALESCE(value, '(not set)')
       END as value_status,
       value_type,
       updated_at
FROM public.qa_app_settings
ORDER BY key;
