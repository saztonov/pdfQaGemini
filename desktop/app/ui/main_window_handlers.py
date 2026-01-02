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
        """Handle add nodes to context"""
        if not node_ids:
            return
        
        new_count = 0
        for node_id in node_ids:
            if node_id not in self.context_node_ids:
                self.context_node_ids.append(node_id)
                new_count += 1
        
        if self.supabase_repo and self.current_conversation_id:
            try:
                await self.supabase_repo.qa_add_nodes(
                    str(self.current_conversation_id),
                    node_ids
                )
            except Exception as e:
                logger.error(f"Ошибка сохранения узлов в БД: {e}")
                self.toast_manager.error(f"Ошибка сохранения: {e}")
                return
        
        if self.right_panel:
            self.right_panel.set_context_node_ids(self.context_node_ids)
            await self.right_panel.load_node_files()
        else:
            self.toast_manager.success(f"В контекст добавлено {len(node_ids)} документов")
    
    @asyncSlot(list)
    async def _on_files_add_context(self: "MainWindow", files_info: list[dict]):
        """Handle add files to context"""
        if not files_info:
            return
        
        logger.info(f"Добавление {len(files_info)} файлов напрямую в контекст")
        
        if self.right_panel:
            await self.right_panel.add_files_to_context(files_info)
        else:
            self.toast_manager.success(f"Добавлено {len(files_info)} файлов в контекст")
    
    @asyncSlot(list)
    async def _on_upload_context_items(self: "MainWindow", item_ids: list):
        """Handle upload context items to Gemini"""
        logger.info(f"=== НАЧАЛО ЗАГРУЗКИ В GEMINI ===")
        logger.info(f"Количество выбранных элементов: {len(item_ids)}")
        logger.info(f"IDs: {item_ids}")
        
        if not self.gemini_client or not self.r2_client:
            logger.error("Сервисы не инициализированы")
            self.toast_manager.error("Сервисы не инициализированы")
            return
        
        if not self.right_panel:
            logger.error("RightPanel не инициализирован")
            self.toast_manager.error("Панель контекста не инициализирована")
            return
        
        logger.info(f"Всего элементов в контексте: {len(self.right_panel.context_items)}")
        
        self.toast_manager.info(f"Загрузка {len(item_ids)} файлов в Gemini...")
        
        uploaded_count = 0
        failed_count = 0
        
        for idx, item_id in enumerate(item_ids, 1):
            try:
                logger.info(f"--- Обработка файла {idx}/{len(item_ids)}: {item_id} ---")
                
                context_item = None
                for item in self.right_panel.context_items:
                    if item.id == item_id:
                        context_item = item
                        break
                
                if not context_item:
                    logger.warning(f"Элемент {item_id} не найден в контексте, пропуск")
                    failed_count += 1
                    continue
                
                logger.info(f"Найден элемент: title={context_item.title}, r2_key={context_item.r2_key}, mime={context_item.mime_type}")
                
                if not context_item.r2_key:
                    logger.warning(f"Элемент {item_id} не имеет r2_key, пропуск")
                    failed_count += 1
                    continue
                
                url = self.r2_client.build_public_url(context_item.r2_key)
                logger.info(f"Скачивание из R2: url={url}")
                
                cached_path = await self.r2_client.download_to_cache(url, item_id)
                logger.info(f"Файл скачан в кэш: {cached_path}, существует={cached_path.exists()}, размер={cached_path.stat().st_size if cached_path.exists() else 0} байт")
                
                logger.info(f"Загрузка в Gemini: mime_type={context_item.mime_type}, display_name={context_item.title}")
                
                result = await self.gemini_client.upload_file(
                    cached_path,
                    mime_type=context_item.mime_type,
                    display_name=context_item.title,
                )
                
                logger.info(f"Gemini результат: name={result.get('name')}, uri={result.get('uri')}")
                
                gemini_name = result["name"]
                gemini_uri = result["uri"]
                
                if self.right_panel:
                    self.right_panel.update_context_item_status(
                        item_id,
                        "uploaded",
                        gemini_name
                    )
                    logger.info(f"Статус элемента обновлен: uploaded, gemini_name={gemini_name}")
                
                if self.supabase_repo and self.current_conversation_id and context_item.node_file_id:
                    try:
                        await self.supabase_repo.qa_save_context_file(
                            str(self.current_conversation_id),
                            str(context_item.node_file_id),
                            gemini_name=gemini_name,
                            gemini_uri=gemini_uri,
                            status="uploaded",
                        )
                    except Exception as e:
                        logger.error(f"Ошибка сохранения статуса в БД: {e}")
                
                self.attached_gemini_files.append({
                    "gemini_name": gemini_name,
                    "gemini_uri": gemini_uri,
                    "context_item_id": item_id,
                    "mime_type": context_item.mime_type,
                })
                
                uploaded_count += 1
                logger.info(f"✓ Файл {idx}/{len(item_ids)} успешно загружен")
            
            except Exception as e:
                logger.error(f"✗ Ошибка загрузки файла {item_id}: {e}", exc_info=True)
                failed_count += 1
                self.toast_manager.error(f"Ошибка файла {idx}: {e}")
        
        logger.info(f"=== ЗАВЕРШЕНИЕ ЗАГРУЗКИ: успешно={uploaded_count}, ошибок={failed_count} ===")
        
        if uploaded_count > 0:
            self.toast_manager.success(f"Загружено {uploaded_count} файлов в Gemini")
        if failed_count > 0:
            self.toast_manager.warning(f"Не удалось загрузить {failed_count} файлов")
    
    @asyncSlot(str, str, str)
    async def _on_ask_model(self: "MainWindow", user_text: str, model_name: str, thinking_level: str):
        """Handle ask model request with streaming thoughts"""
        logger.info(f"=== _on_ask_model ===")
        logger.info(f"  user_text: {user_text[:50]}...")
        logger.info(f"  model_name: {model_name}")
        logger.info(f"  thinking_level: {thinking_level}")
        
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
        
        self.toast_manager.info(f"Отправка запроса модели {model_name} (thinking: {thinking_level})...")
        
        try:
            file_refs = []
            logger.info(f"  attached_gemini_files: {len(self.attached_gemini_files)}")
            for gf in self.attached_gemini_files:
                file_refs.append({
                    "uri": gf["gemini_uri"],
                    "mime_type": gf.get("mime_type", "application/pdf"),
                })
            
            if not file_refs and self.right_panel and self.right_panel.gemini_files:
                logger.info(f"  Используем gemini_files из right_panel: {len(self.right_panel.gemini_files)}")
                for gf in self.right_panel.gemini_files:
                    uri = gf.get("uri")
                    if uri:
                        file_refs.append({
                            "uri": uri,
                            "mime_type": gf.get("mime_type", "application/octet-stream"),
                        })
                if file_refs:
                    self.toast_manager.info(f"Используется {len(file_refs)} файлов из Gemini Files")
            
            if not file_refs:
                self.toast_manager.warning("Внимание: нет загруженных файлов в Gemini. Модель будет отвечать без контекста документов.")
            
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
                }
                self.chat_panel.add_assistant_message(full_answer, meta)
            
            self.toast_manager.success("Ответ получен")
        
        except Exception as e:
            logger.error(f"Ошибка запроса: {e}", exc_info=True)
            self.toast_manager.error(f"Ошибка запроса: {e}")
            if self.chat_panel:
                self.chat_panel.add_system_message(f"Ошибка: {e}", "error")
        
        finally:
            if self.chat_panel:
                self.chat_panel.set_input_enabled(True)
