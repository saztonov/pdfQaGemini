"""Realtime event handlers for main window"""

import asyncio
import logging
from datetime import datetime

from app.services.realtime_client import JobUpdate, MessageUpdate, ArtifactUpdate
from app.services.trace import ModelTrace

logger = logging.getLogger(__name__)


class RealtimeHandlersMixin:
    """Mixin for realtime event handling in server mode"""

    def _on_job_updated(self, job_update: JobUpdate):
        """Handle job status update from realtime"""
        logger.info(f"Job update received: {job_update.job_id} -> {job_update.status}")

        # Only process if this is for the current conversation
        if self.current_conversation_id and job_update.conversation_id != str(
            self.current_conversation_id
        ):
            return

        if job_update.status == "completed":
            # Clear active job to cancel timeout fallback
            if self._active_job_id == job_update.job_id:
                self._active_job_id = None

            # Job completed - hide loading indicator and enable input
            if self.chat_panel:
                self.chat_panel.set_loading(False)
                self.chat_panel.set_input_enabled(True)

            # Note: Don't show result_text here - it will come via _on_realtime_message
            # to avoid duplicate messages. Only log completion.
            logger.info(f"Job {job_update.job_id} completed via Realtime")

        elif job_update.status == "failed":
            # Clear active job to cancel timeout fallback
            if self._active_job_id == job_update.job_id:
                self._active_job_id = None

            # Job failed - show error and enable input
            if self.chat_panel:
                self.chat_panel.set_loading(False)
                self.chat_panel.set_input_enabled(True)
                self.chat_panel.add_system_message(
                    f"Ошибка: {job_update.error_message or 'Неизвестная ошибка'}", "error"
                )

            error_msg = job_update.error_message or "Неизвестная ошибка"
            self.toast_manager.error(f"Ошибка: {error_msg}")
            logger.error(f"Job {job_update.job_id} failed: {error_msg}")

        elif job_update.status == "processing":
            # Job started processing
            logger.info(f"Job {job_update.job_id} is processing")

    def _on_realtime_message(self, message_update: MessageUpdate):
        """Handle new message from realtime"""
        logger.info(
            f"[INSPECTOR] _on_realtime_message called: {message_update.message_id}, "
            f"role={message_update.role}"
        )

        # Only process if this is for the current conversation
        if self.current_conversation_id and message_update.conversation_id != str(
            self.current_conversation_id
        ):
            return

        # Clear active job to prevent timeout fallback from duplicating the message
        if message_update.role == "assistant":
            self._active_job_id = None

        # Add message to chat panel
        if self.chat_panel and message_update.role == "assistant":
            from app.utils.time_utils import format_time

            # Hide loading and enable input
            self.chat_panel.set_loading(False)
            self.chat_panel.set_input_enabled(True)

            # Add message_id to meta for deduplication
            msg_meta = dict(message_update.meta) if message_update.meta else {}
            msg_meta["message_id"] = message_update.message_id

            self.chat_panel.add_message(
                role="assistant",
                content=message_update.content,
                meta=msg_meta,
                timestamp=format_time(datetime.utcnow(), "%H:%M:%S"),
            )

            # Update token counter
            if message_update.meta:
                self.chat_panel.add_tokens(
                    input_tokens=message_update.meta.get("input_tokens", 0),
                    output_tokens=message_update.meta.get("output_tokens", 0)
                )

            self.toast_manager.success("✓ Ответ получен")

            # Create trace for inspector
            self._create_trace_from_response(message_update)

            # Process actions if present
            if message_update.meta and message_update.meta.get("actions"):
                actions = message_update.meta["actions"]
                asyncio.create_task(self._process_model_actions(actions))

    def _on_realtime_artifact(self, artifact_update: ArtifactUpdate):
        """Handle new artifact from realtime (crop previews / ROI)"""
        # Only process if this is for the current conversation
        if self.current_conversation_id and artifact_update.conversation_id != str(
            self.current_conversation_id
        ):
            return

        if not self.chat_panel or not self.r2_client:
            return

        if not artifact_update.r2_key:
            return

        url = self.r2_client.build_public_url(artifact_update.r2_key)
        meta = artifact_update.metadata or {}
        caption = (meta.get("reason") or meta.get("goal") or "").strip()
        crop_id = meta.get("context_item_id") or artifact_update.artifact_id

        # Render as an in-chat preview block
        if artifact_update.mime_type.startswith("image/"):
            self.chat_panel.add_crop_preview(
                crop_url=url,
                crop_id=crop_id,
                caption=caption,
            )

    def _create_trace_from_response(self, message_update: MessageUpdate):
        """Create a trace from server response for inspector"""
        logger.info(
            f"[INSPECTOR] _create_trace_from_response called, "
            f"pending_request={self._pending_request is not None}"
        )

        if not self._pending_request:
            logger.warning("[INSPECTOR] No pending request for trace - skipping")
            return

        try:
            meta = message_update.meta or {}
            request_ts = self._pending_request.get("ts", datetime.utcnow())
            response_ts = datetime.utcnow()
            latency_ms = (response_ts - request_ts).total_seconds() * 1000

            # Build file refs for trace
            file_refs = self._pending_request.get("file_refs", [])
            input_files = [
                {
                    "name": f.get("name", ""),
                    "uri": f.get("uri", ""),
                    "mime_type": f.get("mime_type", ""),
                    "display_name": f.get("display_name", ""),
                }
                for f in file_refs
            ]

            trace = ModelTrace(
                ts=request_ts,
                conversation_id=self.current_conversation_id,
                client_id=self.client_id,
                model=self._pending_request.get("model_name", "unknown"),
                thinking_level=self._pending_request.get("thinking_level", "low"),
                system_prompt=self._pending_request.get("system_prompt", ""),
                user_text=self._pending_request.get("user_text", ""),
                input_files=input_files,
                response_json={
                    "assistant_text": message_update.content,
                    "actions": meta.get("actions", []),
                },
                parsed_actions=meta.get("actions", []),
                latency_ms=latency_ms,
                is_final=meta.get("is_final", True),
                assistant_text=message_update.content,
                full_thoughts=meta.get("thoughts", ""),
                input_tokens=meta.get("input_tokens"),
                output_tokens=meta.get("output_tokens"),
                total_tokens=meta.get("total_tokens"),
            )

            self.trace_store.add(trace)
            logger.info(
                f"[INSPECTOR] Trace created and added: {trace.id}, "
                f"total traces: {self.trace_store.count()}"
            )

            # Clear pending request
            self._pending_request = None

        except Exception as e:
            logger.error(f"[INSPECTOR] Failed to create trace: {e}", exc_info=True)

    def _on_realtime_status(self, is_connected: bool):
        """Handle realtime connection status change"""
        if is_connected:
            logger.info("Realtime connected")
            if self.connection_status:
                self.connection_status.set_server_connected(self.client_id)
        else:
            logger.warning("Realtime disconnected")
            self.toast_manager.warning("Соединение с сервером потеряно")
            if self.connection_status:
                self.connection_status.set_server_disconnected()
