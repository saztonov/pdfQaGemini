"""Upload handlers for MainWindow"""
import logging
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from qasync import asyncSlot

from app.services.bundle_builder import DocumentBundleBuilder
from app.models.schemas import FileType

# Add shared module to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "shared"))
from token_counter import count_tokens_file, count_tokens_bytes

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


class UploadHandlersMixin:
    """Mixin for file upload handlers"""

    @asyncSlot(list)
    async def _on_nodes_add_context(self: "MainWindow", node_ids: list[str]):
        """Handle add nodes to context - build bundle and upload to Gemini"""
        if not node_ids:
            return

        if not self.supabase_repo:
            self.toast_manager.error("Supabase не инициализирован")
            return

        # Check required services based on mode
        if self.server_mode:
            if not self.api_client or not self.r2_client:
                self.toast_manager.error("Сервисы не инициализированы")
                return
        else:
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

    async def _build_and_upload_bundle(self: "MainWindow", node_files: list, node_ids: list[str]):
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
            doc_name = (
                first_file.file_name.rsplit(".", 1)[0] if first_file.file_name else "document"
            )

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
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as tmp_file:
            tmp_file.write(bundle_bytes)
            tmp_path = Path(tmp_file.name)

        try:
            # Upload bundle to Gemini
            self.toast_manager.info("Загрузка bundle.txt в Gemini...")

            if self.server_mode:
                # Server mode: upload via API
                if not self.current_conversation_id:
                    self.toast_manager.error("Нет активного чата для загрузки bundle")
                    return

                result = await self.api_client.upload_file(
                    file_path=str(tmp_path),
                    conversation_id=str(self.current_conversation_id),
                    file_name=bundle_file_name,
                    mime_type="text/plain",
                )
                # Server returns GeminiFileResponse with gemini_name, gemini_uri
                gemini_name = result.get("gemini_name")
                gemini_uri = result.get("gemini_uri", "")
                logger.info(f"Bundle uploaded via server: {gemini_name}")
            else:
                # Local mode: upload directly
                result = await self.gemini_client.upload_file(
                    tmp_path,
                    mime_type="text/plain",
                    display_name=bundle_file_name,
                )
                gemini_name = result.get("name")
                gemini_uri = result.get("uri", "")
                logger.info(f"Bundle uploaded: {gemini_name}")

                # Save metadata to database (only in local mode, server does this automatically)
                if self.supabase_repo and gemini_name:
                    # Use first node_file id as source reference
                    source_node_file_id = str(node_files[0].id) if node_files else None

                    # Count tokens using tiktoken
                    token_count = count_tokens_bytes(bundle_bytes)

                    gemini_file_result = await self.supabase_repo.qa_upsert_gemini_file(
                        gemini_name=gemini_name,
                        gemini_uri=gemini_uri,
                        display_name=bundle_file_name,
                        mime_type="text/plain",
                        size_bytes=len(bundle_bytes),
                        token_count=token_count,
                        source_node_file_id=source_node_file_id,
                        source_r2_key=None,
                        expires_at=None,
                        client_id=self.client_id,
                    )

                    # Store crop_index in metadata for later use
                    if gemini_file_result and crop_index:
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
                conv_id = (
                    str(self.current_conversation_id) if self.current_conversation_id else None
                )
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

        # Check required services based on mode
        if self.server_mode:
            if not self.api_client:
                logger.error("API клиент не инициализирован")
                self.toast_manager.error("API клиент не инициализирован")
                return
            if not self.r2_client:
                logger.error("R2 клиент не инициализирован")
                self.toast_manager.error("R2 клиент не инициализирован")
                return
        else:
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

                # Upload to Gemini (via server API or directly)
                logger.info(f"[{idx}/{len(files_info)}] Загрузка в Gemini: {file_name}")

                if self.server_mode:
                    # Server mode: upload via API (server handles Gemini + DB save)
                    if not self.current_conversation_id:
                        logger.warning("Нет активного чата для загрузки файла")
                        failed_count += 1
                        continue

                    result = await self.api_client.upload_file(
                        file_path=str(cached_path),
                        conversation_id=str(self.current_conversation_id),
                        file_name=file_name,
                        mime_type=mime_type,
                    )
                    # Server returns GeminiFileResponse with gemini_name, gemini_uri
                    gemini_name = result.get("gemini_name")
                    gemini_uri = result.get("gemini_uri", "")
                    logger.info(f"[{idx}/{len(files_info)}] ✓ Загружен через сервер: {gemini_name}")
                else:
                    # Local mode: upload directly to Gemini
                    result = await self.gemini_client.upload_file(
                        cached_path,
                        mime_type=mime_type,
                        display_name=file_name,
                    )
                    gemini_name = result.get("name")
                    gemini_uri = result.get("uri", "")
                    logger.info(f"[{idx}/{len(files_info)}] ✓ Загружен: {gemini_name}")

                    # Save metadata to database (only in local mode, server does this automatically)
                    if self.supabase_repo and gemini_name:
                        try:
                            node_file_id = file_info.get("id")

                            # Count tokens using tiktoken
                            token_count = count_tokens_file(cached_path)

                            gemini_file_result = await self.supabase_repo.qa_upsert_gemini_file(
                                gemini_name=gemini_name,
                                gemini_uri=gemini_uri,
                                display_name=file_name,
                                mime_type=mime_type,
                                size_bytes=result.get("size_bytes"),
                                token_count=token_count,
                                source_node_file_id=node_file_id,
                                source_r2_key=r2_key,
                                expires_at=None,
                                client_id=self.client_id,
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
