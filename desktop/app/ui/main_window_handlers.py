"""Event handlers for MainWindow"""
import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from qasync import asyncSlot

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


class MainWindowHandlers:
    """Mixin for MainWindow event handlers"""
    
    @asyncSlot(list)
    async def _on_nodes_add_context(self: "MainWindow", node_ids: list[str]):
        """Handle add nodes to context - load files and upload to Gemini"""
        if not node_ids:
            return
        
        if not self.supabase_repo:
            self.toast_manager.error("Supabase не инициализирован")
            return
        
        self.toast_manager.info(f"Загрузка файлов для {len(node_ids)} узлов...")
        
        try:
            # Fetch node files for selected nodes
            node_files = await self.supabase_repo.fetch_node_files(node_ids)
            
            if not node_files:
                self.toast_manager.warning("Нет файлов для загрузки")
                return
            
            # Convert to files_info format and upload
            files_info = []
            for nf in node_files:
                files_info.append({
                    "id": str(nf.id),
                    "r2_key": nf.r2_key,
                    "file_name": nf.file_name,
                    "file_type": nf.file_type,
                    "mime_type": nf.mime_type,
                    "node_id": nf.node_id,
                })
            
            await self._upload_files_to_gemini(files_info)
            
        except Exception as e:
            logger.error(f"Ошибка загрузки файлов узлов: {e}", exc_info=True)
            self.toast_manager.error(f"Ошибка: {e}")
    
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
                        await self.supabase_repo.qa_upsert_gemini_file(
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
                    except Exception as e:
                        logger.error(f"  Не удалось сохранить метаданные в БД: {e}")
                
                uploaded_count += 1
                if gemini_name:
                    uploaded_names.append(gemini_name)
            
            except Exception as e:
                logger.error(f"✗ Ошибка загрузки {file_info.get('file_name', '?')}: {e}", exc_info=True)
                failed_count += 1
        
        # Refresh Gemini Files panel
        if self.right_panel:
            await self.right_panel.refresh_files()
            
            # Auto-select newly uploaded files
            for name in uploaded_names:
                self.right_panel.select_file_for_request(name)
            
            # Sync to chat panel
            self._sync_files_to_chat()
        
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
    
    @asyncSlot(list)
    async def _on_upload_context_items(self: "MainWindow", item_ids: list):
        """Legacy handler - no longer used"""
        pass
    
    @asyncSlot(str, str, str, object, list)
    async def _on_ask_model(self: "MainWindow", user_text: str, model_name: str, thinking_level: str, thinking_budget: int, file_refs: list):
        """Handle ask model request with streaming thoughts"""
        logger.info(f"=== _on_ask_model ===")
        logger.info(f"  user_text: {user_text[:50]}...")
        logger.info(f"  model_name: {model_name}")
        logger.info(f"  thinking_level: {thinking_level}")
        logger.info(f"  thinking_budget: {thinking_budget}")
        logger.info(f"  file_refs: {len(file_refs)}")
        
        if not user_text.strip():
            self.toast_manager.warning("Пустое сообщение")
            return
        
        if not self.agent:
            self.toast_manager.error("Агент не инициализирован. Нажмите 'Подключиться'.")
            return
        
        if not self.current_conversation_id:
            self.toast_manager.warning("Нет активного разговора")
            return
        
        if self.chat_panel:
            self.chat_panel.set_input_enabled(False)
            self.chat_panel.add_user_message(user_text)
        
        # Use file_refs from ChatPanel (already selected by user)
        if not file_refs:
            self.toast_manager.warning("⚠️ Нет выбранных файлов. Модель ответит без контекста документов.")
        else:
            self.toast_manager.info(f"Запрос с {len(file_refs)} файлами...")
        
        try:
            has_thoughts = False
            full_answer = ""
            
            if self.chat_panel:
                self.chat_panel.start_thinking_block()
            
            async for chunk in self.agent.ask_stream(
                conversation_id=self.current_conversation_id,
                user_text=user_text,
                file_refs=file_refs,
                model=model_name,
                thinking_level=thinking_level,
                thinking_budget=thinking_budget,
            ):
                chunk_type = chunk.get("type", "")
                content = chunk.get("content", "")
                
                if chunk_type == "thought":
                    has_thoughts = True
                    if self.chat_panel:
                        self.chat_panel.append_thought_chunk(content)
                
                elif chunk_type == "text":
                    full_answer += content
                    if self.chat_panel:
                        self.chat_panel.append_answer_chunk(content)
                
                elif chunk_type == "done":
                    break
                
                elif chunk_type == "error":
                    raise Exception(content)
            
            if self.chat_panel:
                if has_thoughts:
                    self.chat_panel.finish_thinking_block()
                
                meta = {
                    "model": model_name,
                    "thinking_level": thinking_level,
                    "is_final": True,
                    "files_count": len(file_refs),
                }
                self.chat_panel.add_assistant_message(full_answer, meta)
            
            self.toast_manager.success("✓ Ответ получен")
        
        except Exception as e:
            logger.error(f"Ошибка запроса: {e}", exc_info=True)
            self.toast_manager.error(f"Ошибка: {e}")
            if self.chat_panel:
                self.chat_panel.add_system_message(f"Ошибка: {e}", "error")
        
        finally:
            if self.chat_panel:
                self.chat_panel.set_input_enabled(True)
