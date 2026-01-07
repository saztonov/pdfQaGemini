"""Files management mixin for RightContextPanel"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from PySide6.QtWidgets import QTableWidgetItem
from PySide6.QtCore import Qt
from qasync import asyncSlot

logger = logging.getLogger(__name__)


class RightPanelFilesMixin:
    """Mixin with files management methods for RightContextPanel"""

    def _toggle_files_section(self):
        """Toggle files table visibility"""
        is_visible = self.table.isVisible()
        self.table.setVisible(not is_visible)
        self.btn_toggle_files.setText("▲ Файлы чата" if not is_visible else "▼ Файлы чата")

    def _on_files_table_selection_changed(self):
        """Handle files table selection change"""
        selected = len(self.table.selectedItems()) > 0
        self.btn_delete_files.setEnabled(selected)

    @asyncSlot()
    async def _on_refresh_files_clicked(self):
        """Handle refresh files button"""
        if self.conversation_id:
            await self.refresh_files(conversation_id=self.conversation_id)

    @asyncSlot()
    async def _on_delete_files_clicked(self):
        """Handle delete files button"""
        await self.delete_selected_files()

    def _on_cell_changed(self, row: int, col: int):
        """Handle checkbox change"""
        if col != 0:
            return

        item = self.table.item(row, 0)
        if not item:
            return

        name_item = self.table.item(row, 1)
        if not name_item:
            return

        file_name = name_item.data(Qt.UserRole)
        if not file_name:
            return

        checked = item.checkState() == Qt.Checked
        if checked:
            self._selected_for_request.add(file_name)
        else:
            self._selected_for_request.discard(file_name)

        self._update_files_count()
        self._emit_selection()

    def _emit_selection(self):
        """Emit selected files for request"""
        selected = self.get_selected_files_for_request()
        self.filesSelectionChanged.emit(selected)

    async def refresh_files(self, conversation_id: Optional[str] = None):
        """Refresh Gemini Files list (filtered by conversation if provided)"""
        # Check required services based on mode
        if self.server_mode:
            if not self.api_client:
                return
        else:
            if not self.gemini_client:
                return

        try:
            # Get all files from Gemini
            if self.server_mode:
                all_files_raw = await self.api_client.list_gemini_files()
                # Normalize server response (gemini_name -> name, gemini_uri -> uri)
                all_files = [
                    {
                        "name": f.get("gemini_name"),
                        "uri": f.get("gemini_uri"),
                        "display_name": f.get("display_name"),
                        "mime_type": f.get("mime_type"),
                        "size_bytes": f.get("size_bytes"),
                        "token_count": f.get("token_count"),
                        "expiration_time": f.get("expiration_time"),
                    }
                    for f in all_files_raw
                ]
            else:
                all_files = await self.gemini_client.list_files()

            # Filter files by conversation if specified
            if conversation_id and self.supabase_repo:
                self.conversation_id = conversation_id
                try:
                    conv_files = await self.supabase_repo.qa_get_conversation_files(conversation_id)
                    # Build lookup by gemini_name to get display_name from DB
                    db_files_map = {
                        f.get("gemini_name"): f for f in conv_files if f.get("gemini_name")
                    }

                    # Filter and merge data: expiration_time from Gemini, display_name/token_count from DB
                    merged_files = []
                    for f in all_files:
                        name = f.get("name")
                        if name in db_files_map:
                            db_file = db_files_map[name]
                            merged_files.append({
                                "name": name,
                                "uri": f.get("uri"),
                                "display_name": db_file.get("display_name") or f.get("display_name"),
                                "mime_type": db_file.get("mime_type") or f.get("mime_type"),
                                "size_bytes": db_file.get("size_bytes") or f.get("size_bytes"),
                                "token_count": db_file.get("token_count") or f.get("token_count"),
                                "expiration_time": f.get("expiration_time"),
                            })

                    self.gemini_files = merged_files

                    logger.info(
                        f"Отфильтровано {len(self.gemini_files)} из {len(all_files)} файлов для чата {conversation_id}"
                    )
                except Exception as e:
                    logger.error(f"Ошибка фильтрации файлов по чату: {e}", exc_info=True)
                    self.gemini_files = all_files
            else:
                self.gemini_files = all_files

            self._update_table()
            self._update_files_count()

        except Exception as e:
            logger.error(f"Ошибка загрузки Gemini Files: {e}", exc_info=True)

    def _update_table(self):
        """Update table with current files"""
        self.table.blockSignals(True)
        self.table.setRowCount(0)

        for gf in self.gemini_files:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Checkbox column
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            file_name = gf.get("name", "")
            if file_name in self._selected_for_request:
                check_item.setCheckState(Qt.Checked)
            else:
                check_item.setCheckState(Qt.Unchecked)
            self.table.setItem(row, 0, check_item)

            # File name
            display_name = gf.get("display_name") or gf.get("name", "")
            name_item = QTableWidgetItem(display_name)
            name_item.setData(Qt.UserRole, gf.get("name"))
            name_item.setData(Qt.UserRole + 1, gf.get("uri"))
            name_item.setData(Qt.UserRole + 2, gf.get("mime_type"))
            name_item.setData(Qt.UserRole + 3, gf)
            self.table.setItem(row, 1, name_item)

            # MIME
            mime_type = gf.get("mime_type", "")[:30]
            self.table.setItem(row, 2, QTableWidgetItem(mime_type))

            # Size
            size_bytes = gf.get("size_bytes", 0) or 0
            if size_bytes:
                if size_bytes > 1024 * 1024:
                    size_str = f"{size_bytes / (1024*1024):.1f} MB"
                elif size_bytes > 1024:
                    size_str = f"{size_bytes / 1024:.1f} KB"
                else:
                    size_str = f"{size_bytes} B"
            else:
                size_str = "-"
            self.table.setItem(row, 3, QTableWidgetItem(size_str))

            # Token count from DB or estimate
            token_count = gf.get("token_count")
            if token_count:
                # Exact count from tiktoken
                if token_count >= 1_000_000:
                    tokens_str = f"{token_count / 1_000_000:.1f}M"
                elif token_count >= 1000:
                    tokens_str = f"{token_count / 1000:.1f}k"
                else:
                    tokens_str = str(token_count)
            elif size_bytes:
                # Fallback: estimate from size (~4 bytes per token)
                estimated_tokens = size_bytes // 4
                if estimated_tokens >= 1_000_000:
                    tokens_str = f"~{estimated_tokens / 1_000_000:.1f}M"
                elif estimated_tokens >= 1000:
                    tokens_str = f"~{estimated_tokens / 1000:.1f}k"
                else:
                    tokens_str = f"~{estimated_tokens}"
            else:
                tokens_str = "-"
            self.table.setItem(row, 4, QTableWidgetItem(tokens_str))

            # Expiration time in hours (column 5)
            expiration_time = gf.get("expiration_time")
            if expiration_time:
                try:
                    if isinstance(expiration_time, str):
                        exp_str = expiration_time.replace("Z", "+00:00")
                        exp_dt = datetime.fromisoformat(exp_str)
                    else:
                        exp_dt = expiration_time

                    now = datetime.now(timezone.utc)
                    if exp_dt.tzinfo is None:
                        exp_dt = exp_dt.replace(tzinfo=timezone.utc)

                    time_delta = exp_dt - now
                    hours_remaining = time_delta.total_seconds() / 3600

                    if hours_remaining > 0:
                        hours_str = f"{hours_remaining:.1f}"
                        hours_item = QTableWidgetItem(hours_str)
                        if hours_remaining < 1:
                            hours_item.setForeground(Qt.red)
                        elif hours_remaining < 12:
                            hours_item.setForeground(Qt.yellow)
                        else:
                            hours_item.setForeground(Qt.green)
                    else:
                        hours_str = "Истек"
                        hours_item = QTableWidgetItem(hours_str)
                        hours_item.setForeground(Qt.red)
                except Exception as e:
                    logger.error(f"Ошибка парсинга expiration_time: {e}")
                    hours_item = QTableWidgetItem("?")
            else:
                hours_item = QTableWidgetItem("-")

            self.table.setItem(row, 5, hours_item)

        self.table.blockSignals(False)
        self._update_files_count()

    def _update_files_count(self):
        """Update files count label"""
        count = len(self.gemini_files)
        selected = len(self._selected_for_request)
        if selected > 0:
            self.files_count_label.setText(f"{count} файлов | {selected} выбрано")
        else:
            self.files_count_label.setText(f"{count} файлов")

    async def delete_selected_files(self):
        """Delete selected files from Gemini"""
        # Check required services based on mode
        if self.server_mode:
            if not self.api_client:
                if self.toast_manager:
                    self.toast_manager.error("API клиент не инициализирован")
                return
        else:
            if not self.gemini_client:
                if self.toast_manager:
                    self.toast_manager.error("Клиент Gemini не инициализирован")
                return

        selected_rows = set(item.row() for item in self.table.selectedItems())
        if not selected_rows:
            if self.toast_manager:
                self.toast_manager.warning("Нет выбранных файлов")
            return

        file_names = []
        for row in selected_rows:
            name_item = self.table.item(row, 1)
            if name_item:
                name = name_item.data(Qt.UserRole)
                if name:
                    file_names.append(name)

        if self.toast_manager:
            self.toast_manager.info(f"Удаление {len(file_names)} файлов...")

        try:
            for name in file_names:
                if self.server_mode:
                    await self.api_client.delete_file(name)
                else:
                    await self.gemini_client.delete_file(name)
                self._selected_for_request.discard(name)

                # Delete file metadata and links from database
                if self.supabase_repo:
                    try:
                        await self.supabase_repo.qa_delete_gemini_file_by_name(name)
                    except Exception as e:
                        logger.warning(f"Не удалось удалить метаданные файла из БД: {e}")

            await self.refresh_files(conversation_id=self.conversation_id)
            await self.refresh_chats()

            if self.toast_manager:
                self.toast_manager.success(f"Удалено {len(file_names)} файлов")

        except Exception as e:
            logger.error(f"Ошибка удаления: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка: {e}")

    async def reload_selected_files(self):
        """Delete and re-upload selected files from R2"""
        # Check required services based on mode
        if self.server_mode:
            if not self.api_client or not self.r2_client:
                if self.toast_manager:
                    self.toast_manager.error("Сервисы не инициализированы")
                return
        else:
            if not self.gemini_client or not self.r2_client or not self.supabase_repo:
                if self.toast_manager:
                    self.toast_manager.error("Сервисы не инициализированы")
                return

        selected_rows = set(item.row() for item in self.table.selectedItems())
        if not selected_rows:
            if self.toast_manager:
                self.toast_manager.warning("Нет выбранных файлов")
            return

        files_to_reload = []
        for row in selected_rows:
            name_item = self.table.item(row, 1)
            if name_item:
                name = name_item.data(Qt.UserRole)
                file_data = name_item.data(Qt.UserRole + 3)
                if name and file_data:
                    files_to_reload.append({"name": name, "file_data": file_data, "row": row})

        if not files_to_reload:
            if self.toast_manager:
                self.toast_manager.warning("Нет файлов для перезагрузки")
            return

        if self.toast_manager:
            self.toast_manager.info(f"Перезагрузка {len(files_to_reload)} файлов...")

        success_count = 0
        failed_count = 0

        for file_info in files_to_reload:
            name = file_info["name"]
            file_data = file_info["file_data"]
            row = file_info["row"]
            display_name = file_data.get("display_name", "")

            # Update status
            status_item = self.table.item(row, 6)
            if status_item:
                status_item.setText("🔄 Перезагрузка...")
                status_item.setForeground(Qt.blue)

            try:
                # Get file metadata from database
                logger.info(f"Поиск метаданных для файла: {name}")
                file_metadata = await self._get_file_metadata(name)

                if not file_metadata:
                    error_msg = f"Метаданные не найдены для {display_name}"
                    logger.warning(error_msg)
                    if status_item:
                        status_item.setText(f"✗ {error_msg}")
                        status_item.setForeground(Qt.red)
                    failed_count += 1
                    continue

                r2_key = file_metadata.get("source_r2_key") or file_metadata.get("r2_key")
                mime_type = file_metadata.get("mime_type", "application/octet-stream")

                if not r2_key:
                    error_msg = "R2 key не найден"
                    logger.warning(f"{error_msg} для {display_name}")
                    if status_item:
                        status_item.setText(f"✗ {error_msg}")
                        status_item.setForeground(Qt.red)
                    failed_count += 1
                    continue

                # Check if file exists on R2
                logger.info(f"Проверка существования файла на R2: {r2_key}")
                exists = await self.r2_client.object_exists(r2_key)
                if not exists:
                    error_msg = "Файл не найден на R2"
                    logger.warning(f"{error_msg}: {r2_key}")
                    if status_item:
                        status_item.setText(f"✗ {error_msg}")
                        status_item.setForeground(Qt.red)
                    failed_count += 1
                    continue

                # Delete from Gemini
                logger.info(f"Удаление файла из Gemini: {name}")
                if self.server_mode:
                    await self.api_client.delete_file(name)
                else:
                    await self.gemini_client.delete_file(name)
                self._selected_for_request.discard(name)

                # Download from R2
                logger.info(f"Скачивание файла с R2: {r2_key}")
                url = self.r2_client.build_public_url(r2_key)
                cache_key = file_metadata.get("id") or name
                cached_path = await self.r2_client.download_to_cache(url, cache_key)

                # Re-upload to Gemini
                logger.info(f"Повторная загрузка в Gemini: {display_name}")
                if self.server_mode:
                    # Server mode: upload via API
                    result = await self.api_client.upload_file(
                        file_path=str(cached_path),
                        conversation_id=self.conversation_id or "",
                        file_name=display_name,
                        mime_type=mime_type,
                    )
                    new_name = result.get("gemini_name")
                    logger.info(f"✓ Файл успешно перезагружен через сервер: {new_name}")
                else:
                    # Local mode: upload directly
                    result = await self.gemini_client.upload_file(
                        cached_path,
                        mime_type=mime_type,
                        display_name=display_name,
                    )
                    new_name = result.get("name")
                    logger.info(f"✓ Файл успешно перезагружен: {new_name}")

                    # Update metadata in database (only in local mode)
                    if self.supabase_repo and new_name:
                        try:
                            await self.supabase_repo.qa_upsert_gemini_file(
                                gemini_name=new_name,
                                gemini_uri=result.get("uri", ""),
                                display_name=display_name,
                                mime_type=mime_type,
                                size_bytes=result.get("size_bytes"),
                                source_node_file_id=file_metadata.get("source_node_file_id"),
                                source_r2_key=r2_key,
                                expires_at=None,
                                client_id=self.client_id,
                            )
                        except Exception as e:
                            logger.error(f"Не удалось обновить метаданные в БД: {e}")

                success_count += 1
                if status_item:
                    status_item.setText("✓ Перезагружен")
                    status_item.setForeground(Qt.green)

            except Exception as e:
                logger.error(f"✗ Ошибка перезагрузки {display_name}: {e}", exc_info=True)
                if status_item:
                    status_item.setText(f"✗ Ошибка: {str(e)[:30]}")
                    status_item.setForeground(Qt.red)
                failed_count += 1

        await self.refresh_files(conversation_id=self.conversation_id)
        await self.refresh_chats()

        # Show result
        if success_count > 0 and failed_count == 0:
            if self.toast_manager:
                self.toast_manager.success(f"✓ Перезагружено {success_count} файлов")
        elif success_count > 0 and failed_count > 0:
            if self.toast_manager:
                self.toast_manager.warning(f"Перезагружено {success_count}, ошибок {failed_count}")
        elif failed_count > 0:
            if self.toast_manager:
                self.toast_manager.error(f"✗ Не удалось перезагрузить {failed_count} файлов")

    async def _get_file_metadata(self, gemini_name: str) -> Optional[dict]:
        """Get file metadata from database"""
        if not self.supabase_repo:
            return None

        try:
            def _sync_get():
                client = self.supabase_repo._get_client()
                response = (
                    client.table("qa_gemini_files")
                    .select("*")
                    .eq("gemini_name", gemini_name)
                    .limit(1)
                    .execute()
                )
                if response.data:
                    return response.data[0]
                return None

            return await asyncio.to_thread(_sync_get)
        except Exception as e:
            logger.error(f"Ошибка получения метаданных: {e}", exc_info=True)
            return None

    def get_selected_files_for_request(self) -> list[dict]:
        """Get files selected for request"""
        selected = []
        for gf in self.gemini_files:
            name = gf.get("name", "")
            if name in self._selected_for_request:
                selected.append(
                    {
                        "name": name,
                        "uri": gf.get("uri"),
                        "mime_type": gf.get("mime_type"),
                        "display_name": gf.get("display_name"),
                    }
                )
        return selected

    def select_file_for_request(self, file_name: str):
        """Select specific file for request"""
        self._selected_for_request.add(file_name)
        self._update_table()
        self._emit_selection()

    # Legacy compatibility methods
    @property
    def context_items(self):
        return []

    def set_context_node_ids(self, node_ids: list[str]):
        pass

    async def load_node_files(self):
        pass

    async def add_files_to_context(self, files_info: list[dict]):
        pass

    async def load_context_from_db(self):
        await self.refresh_files(conversation_id=self.conversation_id)

    def update_context_item_status(self, item_id: str, status: str, gemini_name: str = None):
        pass
