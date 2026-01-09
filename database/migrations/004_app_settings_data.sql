-- Script to populate qa_app_settings with actual values
-- Run this after 004_app_settings.sql migration
-- Replace placeholder values with your actual credentials

-- =====================================================
-- IMPORTANT: Replace all <YOUR_...> placeholders below
-- =====================================================

-- Gemini API settings
UPDATE public.qa_app_settings SET value = '<YOUR_GEMINI_API_KEY>' WHERE key = 'gemini_api_key';
UPDATE public.qa_app_settings SET value = 'gemini-2.0-flash' WHERE key = 'default_model';

-- R2 Storage settings
UPDATE public.qa_app_settings SET value = '<YOUR_R2_ACCOUNT_ID>' WHERE key = 'r2_account_id';
UPDATE public.qa_app_settings SET value = '<YOUR_R2_ACCESS_KEY_ID>' WHERE key = 'r2_access_key_id';
UPDATE public.qa_app_settings SET value = '<YOUR_R2_SECRET_ACCESS_KEY>' WHERE key = 'r2_secret_access_key';
UPDATE public.qa_app_settings SET value = '<YOUR_R2_BUCKET_NAME>' WHERE key = 'r2_bucket_name';
UPDATE public.qa_app_settings SET value = '<YOUR_R2_PUBLIC_URL>' WHERE key = 'r2_public_url';

-- Chat settings (history context)
UPDATE public.qa_app_settings SET value = '5' WHERE key = 'max_history_pairs';

-- Worker settings
UPDATE public.qa_app_settings SET value = '10' WHERE key = 'worker_max_jobs';
UPDATE public.qa_app_settings SET value = '300' WHERE key = 'worker_job_timeout';
UPDATE public.qa_app_settings SET value = '3' WHERE key = 'worker_max_retries';

-- =====================================================
-- Verify settings were updated
-- =====================================================
SELECT key,
       CASE WHEN key LIKE '%key%' OR key LIKE '%secret%'
            THEN LEFT(value, 4) || '****'
            ELSE value
       END as value_masked,
       value_type,
       updated_at
FROM public.qa_app_settings
ORDER BY key;
