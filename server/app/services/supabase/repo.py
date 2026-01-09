"""Supabase repository - async data access for server"""

import logging
from typing import Optional
from supabase import create_client, Client

from app.services.supabase.conversation_ops import ConversationOpsMixin
from app.services.supabase.message_ops import MessageOpsMixin
from app.services.supabase.job_ops import JobOpsMixin
from app.services.supabase.gemini_file_ops import GeminiFileOpsMixin
from app.services.supabase.prompts_ops import PromptsOpsMixin
from app.services.supabase.auth_ops import AuthOpsMixin
from app.services.supabase.settings_ops import SettingsOpsMixin

logger = logging.getLogger(__name__)


class SupabaseRepo(
    ConversationOpsMixin,
    MessageOpsMixin,
    JobOpsMixin,
    GeminiFileOpsMixin,
    PromptsOpsMixin,
    AuthOpsMixin,
    SettingsOpsMixin,
):
    """Async Supabase data access layer for server"""

    def __init__(self, url: str, key: str):
        logger.info(f"Initializing SupabaseRepo: url={url[:30]}...")
        self.url = url
        self.key = key
        self._client: Optional[Client] = None

    def _get_client(self) -> Client:
        """Lazy init Supabase client"""
        if self._client is None:
            logger.info("Creating Supabase client...")
            self._client = create_client(self.url, self.key)
            logger.info("Supabase client created")
        return self._client
