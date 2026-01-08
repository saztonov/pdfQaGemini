"""Supabase Realtime client for live updates using async client"""

import asyncio
import logging
from typing import Optional
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal, QTimer

logger = logging.getLogger(__name__)


@dataclass
class JobUpdate:
    """Job status update from realtime"""

    job_id: str
    status: str
    conversation_id: str
    result_message_id: Optional[str] = None
    result_text: Optional[str] = None
    result_actions: Optional[list] = None
    result_is_final: Optional[bool] = None
    error_message: Optional[str] = None


@dataclass
class MessageUpdate:
    """New message from realtime"""

    message_id: str
    conversation_id: str
    role: str
    content: str
    meta: Optional[dict] = None


class RealtimeClient(QObject):
    """
    Supabase Realtime client with Qt signals.

    Subscribes to qa_jobs and qa_messages tables for live updates.
    Emits signals when jobs complete or new messages arrive.
    Uses async Supabase client for Realtime support.
    """

    # Signals
    jobUpdated = Signal(object)  # JobUpdate
    messageReceived = Signal(object)  # MessageUpdate
    connectionStatusChanged = Signal(bool)  # is_connected

    def __init__(self, supabase_url: str, supabase_key: str, client_id: str = "default"):
        super().__init__()
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.client_id = client_id
        self._client = None
        self._jobs_channel = None
        self._messages_channel = None
        self._connected = False
        self._subscribed_conversation_ids: set[str] = set()

    async def connect(self) -> bool:
        """
        Connect to Supabase Realtime using async client.

        Returns True if connection successful.
        """
        try:
            from supabase._async.client import create_client as acreate_client

            logger.info("Connecting to Supabase Realtime...")

            # Create async client
            self._client = await acreate_client(self.supabase_url, self.supabase_key)

            # Connect to realtime
            await self._client.realtime.connect()

            # Subscribe to qa_jobs table changes (UPDATE events for status changes)
            self._jobs_channel = self._client.channel("qa_jobs_changes")
            self._jobs_channel.on_postgres_changes(
                event="UPDATE",
                schema="public",
                table="qa_jobs",
                callback=self._on_job_change,
            )
            await self._jobs_channel.subscribe()

            # Subscribe to qa_messages table changes (INSERT events for new messages)
            self._messages_channel = self._client.channel("qa_messages_changes")
            self._messages_channel.on_postgres_changes(
                event="INSERT",
                schema="public",
                table="qa_messages",
                callback=self._on_message_insert,
            )
            await self._messages_channel.subscribe()

            # No need to call listen() - realtime-py handles it internally after subscribe()

            self._connected = True
            self.connectionStatusChanged.emit(True)
            logger.info("Supabase Realtime connected successfully")
            return True

        except ImportError as e:
            logger.error(f"Failed to import async Supabase client: {e}")
            self._connected = False
            self.connectionStatusChanged.emit(False)
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Supabase Realtime: {e}", exc_info=True)
            self._connected = False
            self.connectionStatusChanged.emit(False)
            return False

    async def disconnect(self):
        """Disconnect from Supabase Realtime"""
        try:
            # Unsubscribe from channels
            if self._jobs_channel:
                await self._jobs_channel.unsubscribe()
                self._jobs_channel = None

            if self._messages_channel:
                await self._messages_channel.unsubscribe()
                self._messages_channel = None

            # Disconnect realtime
            if self._client and self._client.realtime:
                await self._client.realtime.disconnect()

            # Close client
            if self._client:
                await self._client.aclose()
                self._client = None

            self._connected = False
            self.connectionStatusChanged.emit(False)
            logger.info("Realtime client disconnected")

        except Exception as e:
            logger.error(f"Error disconnecting Realtime: {e}", exc_info=True)

    def subscribe_to_conversation(self, conversation_id: str):
        """Add conversation to subscribed list for filtering"""
        self._subscribed_conversation_ids.add(conversation_id)
        logger.debug(f"Subscribed to conversation {conversation_id}")

    def unsubscribe_from_conversation(self, conversation_id: str):
        """Remove conversation from subscribed list"""
        self._subscribed_conversation_ids.discard(conversation_id)
        logger.debug(f"Unsubscribed from conversation {conversation_id}")

    def clear_subscriptions(self):
        """Clear all conversation subscriptions"""
        self._subscribed_conversation_ids.clear()

    @property
    def is_connected(self) -> bool:
        """Check if connected to Realtime"""
        return self._connected

    def _on_job_change(self, payload: dict):
        """Handle job table changes - called from websocket thread"""
        try:
            record = payload.get("record") or payload.get("new", {})
            if not record:
                return

            conversation_id = record.get("conversation_id")
            client_id = record.get("client_id")

            # Filter by client_id
            if client_id != self.client_id:
                return

            # Filter by subscribed conversations (if any)
            if self._subscribed_conversation_ids and conversation_id not in self._subscribed_conversation_ids:
                return

            job_update = JobUpdate(
                job_id=record.get("id"),
                status=record.get("status"),
                conversation_id=conversation_id,
                result_message_id=record.get("result_message_id"),
                result_text=record.get("result_text"),
                result_actions=record.get("result_actions"),
                result_is_final=record.get("result_is_final"),
                error_message=record.get("error_message"),
            )

            logger.info(f"Realtime job update: {job_update.job_id} -> {job_update.status}")

            # Thread-safe emit using QTimer.singleShot to run in main thread
            QTimer.singleShot(0, lambda: self.jobUpdated.emit(job_update))

        except Exception as e:
            logger.error(f"Error handling job change: {e}", exc_info=True)

    def _on_message_insert(self, payload: dict):
        """Handle new message inserts - called from websocket thread"""
        try:
            record = payload.get("record") or payload.get("new", {})
            if not record:
                return

            conversation_id = record.get("conversation_id")

            # Filter by subscribed conversations (if any)
            if self._subscribed_conversation_ids and conversation_id not in self._subscribed_conversation_ids:
                return

            # Only emit for assistant messages (user messages we send ourselves)
            role = record.get("role")
            if role != "assistant":
                return

            message_update = MessageUpdate(
                message_id=record.get("id"),
                conversation_id=conversation_id,
                role=role,
                content=record.get("content", ""),
                meta=record.get("meta"),
            )

            logger.info(f"Realtime new message: {message_update.message_id} in {conversation_id}")

            # Thread-safe emit using QTimer.singleShot to run in main thread
            QTimer.singleShot(0, lambda: self.messageReceived.emit(message_update))

        except Exception as e:
            logger.error(f"Error handling message insert: {e}", exc_info=True)
