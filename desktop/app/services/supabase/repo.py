"""Supabase repository - async data access without RLS"""

import logging
from typing import Optional
from supabase import create_client, Client

from app.services.supabase.tree_ops import TreeOpsMixin
from app.services.supabase.conversation_ops import ConversationOpsMixin
from app.services.supabase.message_ops import MessageOpsMixin
from app.services.supabase.gemini_file_ops import GeminiFileOpsMixin
from app.services.supabase.context_file_ops import ContextFileOpsMixin
from app.services.supabase.artifacts_ops import ArtifactsOpsMixin
from app.services.supabase.trace_ops import TraceOpsMixin
from app.services.supabase.prompts_ops import PromptsOpsMixin
from app.services.supabase.stats_ops import StatsOpsMixin

logger = logging.getLogger(__name__)


class SupabaseRepo(
    TreeOpsMixin,
    ConversationOpsMixin,
    MessageOpsMixin,
    GeminiFileOpsMixin,
    ContextFileOpsMixin,
    ArtifactsOpsMixin,
    TraceOpsMixin,
    PromptsOpsMixin,
    StatsOpsMixin,
):
    """Async Supabase data access layer"""

    def __init__(self, url: str, key: str):
        logger.info(f"Инициализация SupabaseRepo: url={url[:30]}...")
        self.url = url
        self.key = key
        self._client: Optional[Client] = None

    def _get_client(self) -> Client:
        """Lazy init Supabase client"""
        if self._client is None:
            logger.info("Создание Supabase клиента...")
            self._client = create_client(self.url, self.key)
            logger.info("Supabase клиент создан успешно")
        return self._client
