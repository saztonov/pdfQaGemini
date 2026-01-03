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
                                        gemini_file_id=gemini_file_id
                                    )
                                    logger.info(f"  Файл привязан к чату {self.current_conversation_id}")
                                except Exception as e:
                                    logger.error(f"  Не удалось привязать файл к чату: {e}")
                        
                        # Save file copy to R2 chat folder
                        if self.current_conversation_id and self.r2_client:
                            try:
                                await self.r2_client.save_chat_file(
                                    conversation_id=str(self.current_conversation_id),
                                    file_name=file_name,
                                    file_path=cached_path,
                                    mime_type=mime_type
                                )
                                logger.info(f"  Файл сохранен в папку чата на R2")
                            except Exception as e:
                                logger.error(f"  Не удалось сохранить файл в папку чата: {e}")
                    
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
        
        # Create conversation on first message if not exists
        if not self.current_conversation_id:
            await self._ensure_conversation()
            if not self.current_conversation_id:
                self.toast_manager.error("Не удалось создать разговор")
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
            
            # Filter out JSON at the end if present
            import re
            json_pattern = r'\s*\{\s*"assistant_text"\s*:.*?\}\s*$'
            full_answer = re.sub(json_pattern, '', full_answer, flags=re.DOTALL).strip()
            
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
            
            # Update conversation timestamp
            if self.current_conversation_id and self.supabase_repo:
                try:
                    await self.supabase_repo.qa_update_conversation(
                        conversation_id=str(self.current_conversation_id)
                    )
                except Exception as e:
                    logger.warning(f"Не удалось обновить timestamp чата: {e}")
            
            # Save chat messages to R2
            if self.current_conversation_id and self.supabase_repo and self.r2_client:
                try:
                    messages = await self.supabase_repo.qa_list_messages(str(self.current_conversation_id))
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
                    await self.r2_client.save_chat_messages(str(self.current_conversation_id), messages_data)
                    logger.info(f"Переписка сохранена на R2 для чата {self.current_conversation_id}")
                except Exception as e:
                    logger.error(f"Не удалось сохранить переписку на R2: {e}")
        
        except Exception as e:
            logger.error(f"Ошибка запроса: {e}", exc_info=True)
            self.toast_manager.error(f"Ошибка: {e}")
            if self.chat_panel:
                self.chat_panel.add_system_message(f"Ошибка: {e}", "error")
        
        finally:
            if self.chat_panel:
                self.chat_panel.set_input_enabled(True)
