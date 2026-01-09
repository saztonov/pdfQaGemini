"""Agentic loop handlers for MainWindow"""

import json
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from app.services.agent import build_user_prompt

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


class AgenticHandlersMixin:
    """Mixin for agentic loop handlers"""

    async def _run_agentic(
        self: "MainWindow",
        question: str,
        system_prompt: str,
        user_text_template: str,
        model_name: str,
        thinking_level: str,
        thinking_budget: int,
        initial_file_refs: list,
    ):
        """Run agentic loop: request_files → request_roi → final"""
        MAX_ITER = 5
        current_file_refs = list(initial_file_refs)

        # Build context catalog from available crops
        context_catalog = self._build_context_catalog()
        context_catalog_json = json.dumps(context_catalog, ensure_ascii=False, indent=2)

        if not current_file_refs:
            self.toast_manager.warning("⚠️ Нет файлов. Модель ответит без контекста.")
        else:
            self.toast_manager.info(f"Agentic запрос с {len(current_file_refs)} файлами...")

        for iteration in range(MAX_ITER):
            logger.info(f"=== Agentic iteration {iteration + 1}/{MAX_ITER} ===")

            # Build prompt with catalog (only first iteration)
            if iteration == 0:
                # Use user_text_template if provided, otherwise use default
                user_prompt = build_user_prompt(question, context_catalog_json, user_text_template)
            else:
                user_prompt = question  # Follow-up iterations use original question

            # Call agent with structured output
            reply = await self.agent.ask_question(
                conversation_id=self.current_conversation_id,
                user_text=user_prompt,
                file_refs=current_file_refs,
                model=model_name,
                system_prompt=system_prompt,
                thinking_level="low",
                thinking_budget=thinking_budget,
            )

            logger.info(f"  Reply: is_final={reply.is_final}, actions={len(reply.actions)}")

            # Process actions
            should_continue = False

            for action in reply.actions:
                action_type = action.type
                logger.info(f"  Action: {action_type}")

                if action_type == "request_files":
                    # Parse payload for items
                    payload = action.get_request_files_payload()
                    if payload and payload.items:
                        items = [
                            {
                                "context_item_id": item.context_item_id,
                                "kind": item.kind,
                                "reason": item.reason,
                                "priority": item.priority or "medium",
                            }
                            for item in payload.items
                        ]
                        self.toast_manager.info(f"Докачиваю {len(items)} файлов...")
                        new_refs, uploaded_file_infos = await self._fetch_and_upload_crops(items)
                        current_file_refs.extend(new_refs)
                        if uploaded_file_infos:
                            if self.right_panel:
                                conv_id = (
                                    str(self.current_conversation_id)
                                    if self.current_conversation_id
                                    else None
                                )
                                await self.right_panel.refresh_files(conversation_id=conv_id)
                            if self.chat_panel:
                                self.chat_panel.add_selected_files(uploaded_file_infos)
                        should_continue = True
                    else:
                        logger.warning("request_files action without valid payload")

                elif action_type == "request_roi":
                    payload = action.get_request_roi_payload()
                    if payload:
                        self.toast_manager.info("Рендерю ROI...")
                        roi_ref = await self._handle_roi_action_agentic(action, payload)
                        if roi_ref:
                            roi_ref["is_roi"] = True
                            current_file_refs.append(roi_ref)
                            should_continue = True
                    else:
                        logger.warning("request_roi action without valid payload")

                elif action_type == "open_image":
                    payload = action.get_open_image_payload()
                    if payload:
                        self.toast_manager.info(f"Открываю изображение: {payload.context_item_id}")
                        # Just log, actual viewing handled elsewhere if needed

                elif action_type == "final":
                    # Show final answer in chat
                    if self.chat_panel:
                        final_payload = action.get_final_payload()
                        meta = {
                            "model": model_name,
                            "thinking_level": thinking_level,
                            "is_final": True,
                            "iterations": iteration + 1,
                            "files_count": len(current_file_refs),
                        }
                        if final_payload:
                            meta["confidence"] = final_payload.confidence
                            meta["used_context_item_ids"] = final_payload.used_context_item_ids
                        self.chat_panel.add_assistant_message(reply.assistant_text, meta)

                    self.toast_manager.success(f"✓ Ответ получен (итераций: {iteration + 1})")
                    await self._save_conversation_state()
                    return

            # If is_final but no explicit final action, still finish
            if reply.is_final:
                if self.chat_panel:
                    meta = {
                        "model": model_name,
                        "thinking_level": thinking_level,
                        "is_final": True,
                        "iterations": iteration + 1,
                        "files_count": len(current_file_refs),
                    }
                    self.chat_panel.add_assistant_message(reply.assistant_text, meta)
                self.toast_manager.success(f"✓ Ответ получен (итераций: {iteration + 1})")
                await self._save_conversation_state()
                return

            # If no continue actions, show response and exit
            if not should_continue:
                if self.chat_panel:
                    meta = {
                        "model": model_name,
                        "thinking_level": thinking_level,
                        "is_final": reply.is_final,
                        "iterations": iteration + 1,
                        "files_count": len(current_file_refs),
                    }
                    self.chat_panel.add_assistant_message(reply.assistant_text, meta)

                self.toast_manager.success(f"✓ Ответ получен (итераций: {iteration + 1})")
                await self._save_conversation_state()
                return

        # Max iterations reached
        self.toast_manager.warning(f"Достигнут лимит итераций ({MAX_ITER})")
        if self.chat_panel:
            self.chat_panel.add_system_message(f"Лимит итераций ({MAX_ITER}) достигнут", "warning")
        await self._save_conversation_state()

    def _build_context_catalog(self: "MainWindow") -> dict:
        """Build minimal context catalog JSON from available files"""
        catalog = {"crops": [], "text_files": []}

        if not self.right_panel:
            return catalog

        for item in getattr(self.right_panel, "context_items", []):
            entry = {
                "context_item_id": item.id,
                "title": item.title,
                "mime_type": item.mime_type,
            }
            # Classify by mime_type
            if "image" in item.mime_type or "pdf" in item.mime_type:
                catalog["crops"].append(entry)
            else:
                catalog["text_files"].append(entry)

        return catalog

    async def _fetch_and_upload_crops(
        self: "MainWindow", items: list[dict]
    ) -> tuple[list[dict], list[dict]]:
        """Fetch crops from R2 and upload to Gemini, return (file_refs, file_infos)"""
        new_refs = []
        uploaded_file_infos = []

        if not self.r2_client or not self.gemini_client:
            return new_refs, uploaded_file_infos

        for item in items:
            context_item_id = item.get("context_item_id")
            if not context_item_id:
                continue

            # Find context item by id
            context_item = None
            if self.right_panel:
                for ci in getattr(self.right_panel, "context_items", []):
                    if ci.id == context_item_id:
                        context_item = ci
                        break

            if not context_item or not context_item.r2_key:
                logger.warning(f"Context item not found: {context_item_id}")
                continue

            try:
                # Download from R2
                url = self.r2_client.build_public_url(context_item.r2_key)
                cached_path = await self.r2_client.download_to_cache(url, context_item_id)

                # Upload to Gemini
                result = await self.gemini_client.upload_file(
                    cached_path,
                    mime_type=context_item.mime_type,
                    display_name=context_item.title,
                )

                gemini_name = result.get("name")
                gemini_uri = result.get("uri")
                if gemini_uri:
                    new_refs.append(
                        {
                            "uri": gemini_uri,
                            "mime_type": context_item.mime_type,
                        }
                    )
                    # Build file_info for chat panel
                    uploaded_file_infos.append(
                        {
                            "name": gemini_name,
                            "uri": gemini_uri,
                            "mime_type": context_item.mime_type,
                            "display_name": result.get("display_name") or context_item.title,
                        }
                    )
                    logger.info(f"  Uploaded crop: {context_item.title}")

            except Exception as e:
                logger.error(f"Failed to upload crop {context_item_id}: {e}")

        return new_refs, uploaded_file_infos

    async def _handle_roi_action_agentic(self: "MainWindow", action, payload) -> dict | None:
        """Handle ROI action in agentic mode, return file_ref or None"""
        from app.ui.image_viewer import ImageViewerDialog
        from datetime import datetime
        import asyncio

        context_item_id = payload.image_ref.context_item_id
        if not context_item_id:
            return None

        # Find context item
        context_item = None
        if self.right_panel:
            for ci in getattr(self.right_panel, "context_items", []):
                if ci.id == context_item_id:
                    context_item = ci
                    break

        if not context_item or not context_item.r2_key:
            self.toast_manager.warning(f"Context item не найден: {context_item_id}")
            return None

        if not self.r2_client or not self.gemini_client or not self.pdf_renderer:
            self.toast_manager.error("Сервисы не инициализированы")
            return None

        try:
            # Download file
            url = self.r2_client.build_public_url(context_item.r2_key)
            cached_path = await self.r2_client.download_to_cache(url, context_item.id)

            # Render preview
            preview_image = self.pdf_renderer.render_preview(cached_path, page_num=0, dpi=150)

            # Show dialog and wait for result
            result_ref = {"value": None}
            event = asyncio.Event()

            dialog = ImageViewerDialog(self)
            dialog.load_image(preview_image)

            # Build suggestion dict for viewer
            suggestion = {
                "type": action.type,
                "goal": payload.goal,
                "note": action.note or payload.goal,
            }
            if payload.suggested_bbox_norm:
                suggestion["suggested_bbox_norm"] = {
                    "x1": payload.suggested_bbox_norm.x1,
                    "y1": payload.suggested_bbox_norm.y1,
                    "x2": payload.suggested_bbox_norm.x2,
                    "y2": payload.suggested_bbox_norm.y2,
                }
            dialog.set_model_suggestions([suggestion])

            # DPI from payload
            target_dpi = payload.dpi or 400

            async def on_roi_selected(bbox, note):
                # Render ROI at target DPI
                roi_png = self.pdf_renderer.render_roi(
                    cached_path, bbox, page_num=0, dpi=target_dpi
                )

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                roi_filename = f"roi_{timestamp}.png"

                # Upload to Gemini
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(roi_png)
                    tmp_path = Path(tmp.name)

                try:
                    upload_result = await self.gemini_client.upload_file(
                        tmp_path, mime_type="image/png", display_name=roi_filename
                    )
                    gemini_uri = upload_result.get("uri")
                    if gemini_uri:
                        result_ref["value"] = {"uri": gemini_uri, "mime_type": "image/png"}
                        self.toast_manager.success(f"ROI загружен: {roi_filename}")
                finally:
                    tmp_path.unlink(missing_ok=True)

                event.set()

            def on_rejected(reason):
                self.toast_manager.info("ROI отклонён пользователем")
                event.set()

            dialog.roiSelected.connect(
                lambda bbox, note: asyncio.create_task(on_roi_selected(bbox, note))
            )
            dialog.roiRejected.connect(on_rejected)

            dialog.show()
            await event.wait()
            dialog.close()

            return result_ref["value"]

        except Exception as e:
            logger.error(f"ROI action failed: {e}")
            self.toast_manager.error(f"Ошибка ROI: {e}")
            return None

    async def _save_conversation_state(self: "MainWindow"):
        """Save conversation state after agentic loop"""
        if not self.current_conversation_id or not self.supabase_repo:
            return

        try:
            await self.supabase_repo.qa_update_conversation(
                conversation_id=str(self.current_conversation_id)
            )
        except Exception as e:
            logger.warning(f"Не удалось обновить timestamp чата: {e}")

        # Save to R2
        if self.r2_client:
            try:
                messages = await self.supabase_repo.qa_list_messages(
                    str(self.current_conversation_id)
                )
                messages_data = [
                    {
                        "id": str(msg.id),
                        "role": msg.role,
                        "content": msg.content,
                        "meta": msg.meta,
                        "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    }
                    for msg in messages
                ]
                await self.r2_client.save_chat_messages(
                    str(self.current_conversation_id), messages_data
                )
            except Exception as e:
                logger.error(f"Не удалось сохранить переписку на R2: {e}")
