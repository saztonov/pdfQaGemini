"""Event handlers for MainWindow"""
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from qasync import asyncSlot

from app.services.bundle_builder import DocumentBundleBuilder
from app.models.schemas import FileType

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


class MainWindowHandlers:
    """Mixin for MainWindow event handlers"""

    @asyncSlot(list)
    async def _on_nodes_add_context(self: "MainWindow", node_ids: list[str]):
        """Handle add nodes to context - build bundle and upload to Gemini"""
        if not node_ids:
            return

        if not self.supabase_repo:
            self.toast_manager.error("Supabase не инициализирован")
            return

        if not self.gemini_client or not self.r2_client:
            self.toast_manager.error("Сервисы не инициализированы")
            return

        self.toast_manager.info(f"Подготовка bundle для {len(node_ids)} узлов...")

        try:
            # Fetch node files for selected nodes
            node_files = await self.supabase_repo.fetch_node_files(node_ids)

            if not node_files:
                self.toast_manager.warning("Нет файлов для загрузки")
                return

            # Build bundle using DocumentBundleBuilder
            await self._build_and_upload_bundle(node_files, node_ids)

        except Exception as e:
            logger.error(f"Ошибка загрузки файлов узлов: {e}", exc_info=True)
            self.toast_manager.error(f"Ошибка: {e}")

    async def _build_and_upload_bundle(
        self: "MainWindow", node_files: list, node_ids: list[str]
    ):
        """Build bundle.txt from node files and upload to Gemini"""
        builder = DocumentBundleBuilder()

        # Select primary text source
        text_source = builder.select_primary_text_source(node_files)
        text_bytes = None
        text_file_type = None

        if text_source:
            logger.info(f"Text source selected: {text_source.file_type} - {text_source.file_name}")
            # Download text file from R2
            try:
                text_bytes = await self.r2_client.download_bytes(text_source.r2_key)
                text_file_type = text_source.file_type
                logger.info(f"Downloaded {len(text_bytes)} bytes from R2")
            except Exception as e:
                logger.error(f"Failed to download text source: {e}")

        # Get crop files
        crop_files = [nf for nf in node_files if nf.file_type == FileType.CROP.value]
        logger.info(f"Found {len(crop_files)} crop files")

        # Get document name from first node
        doc_name = "document"
        if node_files:
            # Try to get meaningful name
            first_file = node_files[0]
            doc_name = first_file.file_name.rsplit(".", 1)[0] if first_file.file_name else "document"

        # Build bundle
        bundle_bytes, crop_index = builder.build_bundle(
            text_file_bytes=text_bytes,
            text_file_type=text_file_type,
            crop_node_files=crop_files,
            document_name=doc_name,
        )

        logger.info(f"Bundle built: {len(bundle_bytes)} bytes, {len(crop_index)} crops")

        # Write bundle to temp file
        bundle_file_name = f"{doc_name}_bundle.txt"
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".txt", delete=False
        ) as tmp_file:
            tmp_file.write(bundle_bytes)
            tmp_path = Path(tmp_file.name)

        try:
            # Upload bundle to Gemini
            self.toast_manager.info("Загрузка bundle.txt в Gemini...")

            result = await self.gemini_client.upload_file(
                tmp_path,
                mime_type="text/plain",
                display_name=bundle_file_name,
            )

            gemini_name = result.get("name")
            gemini_uri = result.get("uri", "")
            logger.info(f"Bundle uploaded: {gemini_name}")

            # Save metadata to database
            if self.supabase_repo and gemini_name:
                # Use first node_file id as source reference
                source_node_file_id = str(node_files[0].id) if node_files else None

                gemini_file_result = await self.supabase_repo.qa_upsert_gemini_file(
                    gemini_name=gemini_name,
                    gemini_uri=gemini_uri,
                    display_name=bundle_file_name,
                    mime_type="text/plain",
                    size_bytes=len(bundle_bytes),
                    source_node_file_id=source_node_file_id,
                    source_r2_key=None,
                    expires_at=None,
                )

                # Store crop_index in metadata for later use
                if gemini_file_result and crop_index:
                    # Could store crop_index in gemini_file metadata if needed
                    logger.info(f"Crop index: {len(crop_index)} items stored")

                # Attach to conversation
                if self.current_conversation_id and gemini_file_result:
                    gemini_file_id = gemini_file_result.get("id")
                    if gemini_file_id:
                        try:
                            await self.supabase_repo.qa_attach_gemini_file(
                                conversation_id=str(self.current_conversation_id),
                                gemini_file_id=gemini_file_id,
                            )
                            logger.info(f"Bundle attached to chat {self.current_conversation_id}")
                        except Exception as e:
                            logger.error(f"Failed to attach bundle: {e}")

            # Refresh panels
            if self.right_panel:
                conv_id = str(self.current_conversation_id) if self.current_conversation_id else None
                await self.right_panel.refresh_files(conversation_id=conv_id)

                if gemini_name:
                    self.right_panel.select_file_for_request(gemini_name)

                self._sync_files_to_chat()
                await self.right_panel.refresh_chats()

            self.toast_manager.success(f"✓ Bundle загружен ({len(bundle_bytes)} bytes)")

        finally:
            # Cleanup temp file
            try:
                tmp_path.unlink()
            except Exception:
                pass

    @asyncSlot(list)
    async def _on_files_add_context(self: "MainWindow", files_info: list[dict]):
        """Handle add files to context - upload directly to Gemini"""
        if not files_info:
            return

        await self._upload_files_to_gemini(files_info)

    async def _upload_files_to_gemini(self: "MainWindow", files_info: list[dict]):
        """Upload files to Gemini and refresh panel"""
        logger.info(f"=== ЗАГРУЗКА {len(files_info)} ФАЙЛОВ В GEMINI ===")

        if not self.gemini_client or not self.r2_client:
            logger.error("Сервисы не инициализированы")
            self.toast_manager.error("Сервисы не инициализированы")
            return

        self.toast_manager.info(f"Загрузка {len(files_info)} файлов в Gemini...")

        uploaded_count = 0
        failed_count = 0
        uploaded_names = []

        for idx, file_info in enumerate(files_info, 1):
            try:
                r2_key = file_info.get("r2_key")
                file_name = file_info.get("file_name", "file")
                mime_type = file_info.get("mime_type", "application/octet-stream")
                file_id = file_info.get("id", str(idx))

                if not r2_key:
                    logger.warning(f"Файл {file_name} не имеет r2_key, пропуск")
                    failed_count += 1
                    continue

                # Download from R2
                url = self.r2_client.build_public_url(r2_key)
                logger.info(f"[{idx}/{len(files_info)}] Скачивание: {file_name}")

                cached_path = await self.r2_client.download_to_cache(url, file_id)

                # Upload to Gemini
                logger.info(f"[{idx}/{len(files_info)}] Загрузка в Gemini: {file_name}")

                result = await self.gemini_client.upload_file(
                    cached_path,
                    mime_type=mime_type,
                    display_name=file_name,
                )

                gemini_name = result.get("name")
                gemini_uri = result.get("uri", "")
                logger.info(f"[{idx}/{len(files_info)}] ✓ Загружен: {gemini_name}")

                # Save metadata to database
                if self.supabase_repo and gemini_name:
                    try:
                        node_file_id = file_info.get("id")
                        gemini_file_result = await self.supabase_repo.qa_upsert_gemini_file(
                            gemini_name=gemini_name,
                            gemini_uri=gemini_uri,
                            display_name=file_name,
                            mime_type=mime_type,
                            size_bytes=result.get("size_bytes"),
                            source_node_file_id=node_file_id,
                            source_r2_key=r2_key,
                            expires_at=None,  # Will be updated on next list
                        )
                        logger.info(f"  Метаданные сохранены в БД для {gemini_name}")

                        # Attach file to current conversation
                        if self.current_conversation_id and gemini_file_result:
                            gemini_file_id = gemini_file_result.get("id")
                            if gemini_file_id:
                                try:
                                    await self.supabase_repo.qa_attach_gemini_file(
                                        conversation_id=str(self.current_conversation_id),
                                        gemini_file_id=gemini_file_id,
                                    )
                                    logger.info(
                                        f"  Файл привязан к чату {self.current_conversation_id}"
                                    )
                                except Exception as e:
                                    logger.error(f"  Не удалось привязать файл к чату: {e}")

                        # Save file copy to R2 chat folder
                        if self.current_conversation_id and self.r2_client:
                            try:
                                await self.r2_client.save_chat_file(
                                    conversation_id=str(self.current_conversation_id),
                                    file_name=file_name,
                                    file_path=cached_path,
                                    mime_type=mime_type,
                                )
                                logger.info("  Файл сохранен в папку чата на R2")
                            except Exception as e:
                                logger.error(f"  Не удалось сохранить файл в папку чата: {e}")

                    except Exception as e:
                        logger.error(f"  Не удалось сохранить метаданные в БД: {e}")

                uploaded_count += 1
                if gemini_name:
                    uploaded_names.append(gemini_name)

            except Exception as e:
                logger.error(
                    f"✗ Ошибка загрузки {file_info.get('file_name', '?')}: {e}", exc_info=True
                )
                failed_count += 1

        # Refresh Gemini Files panel
        if self.right_panel:
            conv_id = str(self.current_conversation_id) if self.current_conversation_id else None
            await self.right_panel.refresh_files(conversation_id=conv_id)

            # Auto-select newly uploaded files
            for name in uploaded_names:
                self.right_panel.select_file_for_request(name)

            # Sync to chat panel
            self._sync_files_to_chat()

            # Refresh chats list to update file count
            await self.right_panel.refresh_chats()

        # Show result
        if uploaded_count > 0:
            self.toast_manager.success(f"✓ Загружено {uploaded_count} файлов в Gemini")
        if failed_count > 0:
            self.toast_manager.warning(f"✗ Не удалось загрузить {failed_count} файлов")

    def _sync_files_to_chat(self: "MainWindow"):
        """Sync available Gemini files to chat panel"""
        if self.right_panel and self.chat_panel:
            files = self.right_panel.gemini_files
            self.chat_panel.set_available_files(files)
            logger.info(f"Синхронизировано {len(files)} файлов с ChatPanel")

    @asyncSlot(list)
    async def _on_upload_context_items(self: "MainWindow", item_ids: list):
        """Legacy handler - no longer used"""
        pass

    @asyncSlot(str, str, str, str, object, list)
    async def _on_ask_model(
        self: "MainWindow",
        user_text: str,
        system_prompt: str,
        model_name: str,
        thinking_level: str,
        thinking_budget: int,
        file_refs: list,
    ):
        """Handle ask model request - agentic loop with structured output"""
        logger.info("=== _on_ask_model (agentic) ===")
        logger.info(f"  user_text: {user_text[:50]}...")
        logger.info(f"  model_name: {model_name}, thinking: {thinking_level}")
        logger.info(f"  file_refs: {len(file_refs)}")

        if not user_text.strip():
            self.toast_manager.warning("Пустое сообщение")
            return

        if not self.agent:
            self.toast_manager.error("Агент не инициализирован. Нажмите 'Подключиться'.")
            return

        # Ensure conversation exists
        if not self.current_conversation_id:
            await self._ensure_conversation()
            if not self.current_conversation_id:
                self.toast_manager.error("Не удалось создать разговор")
                return

        if self.chat_panel:
            self.chat_panel.set_input_enabled(False)
            self.chat_panel.add_user_message(user_text)

        try:
            await self._run_agentic(
                question=user_text,
                system_prompt=system_prompt,
                model_name=model_name,
                thinking_level=thinking_level,
                thinking_budget=thinking_budget,
                initial_file_refs=file_refs,
            )
        except Exception as e:
            logger.error(f"Ошибка agentic loop: {e}", exc_info=True)
            self.toast_manager.error(f"Ошибка: {e}")
            if self.chat_panel:
                self.chat_panel.add_system_message(f"Ошибка: {e}", "error")
        finally:
            if self.chat_panel:
                self.chat_panel.set_input_enabled(True)

    async def _run_agentic(
        self: "MainWindow",
        question: str,
        system_prompt: str,
        model_name: str,
        thinking_level: str,
        thinking_budget: int,
        initial_file_refs: list,
    ):
        """Run agentic loop: PLAN → FETCH → ANSWER → ROI → FINAL"""
        MAX_ITER = 4
        current_file_refs = list(initial_file_refs)

        # Build context catalog from available crops
        context_catalog = self._build_context_catalog()

        if not current_file_refs:
            self.toast_manager.warning("⚠️ Нет файлов. Модель ответит без контекста.")
        else:
            self.toast_manager.info(f"Agentic запрос с {len(current_file_refs)} файлами...")

        for iteration in range(MAX_ITER):
            logger.info(f"=== Agentic iteration {iteration + 1}/{MAX_ITER} ===")

            # Build prompt with catalog
            user_prompt = self._build_agentic_prompt(question, context_catalog, iteration)

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
                    items = action.payload.get("items", [])
                    if items:
                        self.toast_manager.info(f"Докачиваю {len(items)} файлов...")
                        new_refs, uploaded_file_infos = await self._fetch_and_upload_crops(items)
                        current_file_refs.extend(new_refs)
                        # Update right panel and auto-select in chat
                        if uploaded_file_infos:
                            if self.right_panel:
                                conv_id = str(self.current_conversation_id) if self.current_conversation_id else None
                                await self.right_panel.refresh_files(conversation_id=conv_id)
                            if self.chat_panel:
                                self.chat_panel.add_selected_files(uploaded_file_infos)
                        should_continue = True

                elif action_type == "request_roi":
                    self.toast_manager.info("Рендерю ROI...")
                    roi_ref = await self._handle_roi_action_agentic(action)
                    if roi_ref:
                        # Mark ROI for high resolution processing
                        roi_ref["is_roi"] = True
                        current_file_refs.append(roi_ref)
                        should_continue = True

                elif action_type == "final":
                    # Show final answer in chat
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
            self.chat_panel.add_system_message(
                f"Лимит итераций ({MAX_ITER}) достигнут", "warning"
            )
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

    def _build_agentic_prompt(
        self: "MainWindow", question: str, catalog: dict, iteration: int
    ) -> str:
        """Build user prompt with context catalog"""
        import json

        prompt_parts = [question]

        if iteration == 0 and (catalog["crops"] or catalog["text_files"]):
            prompt_parts.append("\n\n--- CONTEXT CATALOG ---")
            prompt_parts.append(json.dumps(catalog, ensure_ascii=False, indent=2))
            prompt_parts.append("--- END CATALOG ---")

        return "\n".join(prompt_parts)

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
                    new_refs.append({
                        "uri": gemini_uri,
                        "mime_type": context_item.mime_type,
                    })
                    # Build file_info for chat panel
                    uploaded_file_infos.append({
                        "name": gemini_name,
                        "uri": gemini_uri,
                        "mime_type": context_item.mime_type,
                        "display_name": result.get("display_name") or context_item.title,
                    })
                    logger.info(f"  Uploaded crop: {context_item.title}")

            except Exception as e:
                logger.error(f"Failed to upload crop {context_item_id}: {e}")

        return new_refs, uploaded_file_infos

    async def _handle_roi_action_agentic(
        self: "MainWindow", action
    ) -> dict | None:
        """Handle ROI action in agentic mode, return file_ref or None"""
        from app.ui.image_viewer import ImageViewerDialog
        import tempfile
        from datetime import datetime
        import asyncio

        payload = action.payload
        image_ref = payload.get("image_ref", {})
        context_item_id = image_ref.get("context_item_id") if isinstance(image_ref, dict) else image_ref

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
            return None

        if not self.r2_client or not self.gemini_client or not self.pdf_renderer:
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
            dialog.set_model_suggestions([action])

            async def on_roi_selected(bbox, note):
                # Render ROI at high DPI
                roi_png = self.pdf_renderer.render_roi(cached_path, bbox, page_num=0, dpi=400)

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
                finally:
                    tmp_path.unlink(missing_ok=True)

                event.set()

            def on_rejected(reason):
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
