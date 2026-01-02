"""Model actions handlers (ROI, Image Viewer)"""
import asyncio
import tempfile
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import TYPE_CHECKING

from app.models.schemas import ContextItem

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


class ModelActionsHandler:
    """Mixin for handling model actions"""
    
    async def process_model_actions(self: "MainWindow", actions: list):
        """Process model actions"""
        for action in actions:
            if action.type == "open_image":
                await self._handle_open_image_action(action)
            elif action.type == "request_roi":
                await self._handle_request_roi_action(action)
            elif action.type == "final":
                if self.chat_panel:
                    self.chat_panel.add_system_message("Диалог завершён", "success")
    
    async def _handle_open_image_action(self: "MainWindow", action):
        """Handle open_image action from model"""
        self.toast_manager.info("Открытие изображения...")
        
        try:
            context_item_id = action.payload.get("context_item_id")
            r2_key = action.payload.get("r2_key")
            
            context_item = None
            if context_item_id and self.right_panel:
                for item in self.right_panel.context_items:
                    if item.id == context_item_id:
                        context_item = item
                        break
            
            if not context_item and r2_key:
                context_item = ContextItem(
                    id=hashlib.md5(r2_key.encode()).hexdigest(),
                    title=r2_key.split("/")[-1],
                    r2_key=r2_key,
                    mime_type="application/pdf",
                    status="local"
                )
            
            if not context_item or not context_item.r2_key:
                self.toast_manager.warning("Не удается найти ссылку на файл")
                return
            
            await self._open_image_viewer(context_item, [action])
        
        except Exception as e:
            self.toast_manager.error(f"Ошибка открытия изображения: {e}")
    
    async def _handle_request_roi_action(self: "MainWindow", action):
        """Handle request_roi action from model"""
        self.toast_manager.info("Модель запрашивает выбор области...")
        
        try:
            image_ref = action.payload.get("image_ref") or action.payload.get("context_item_id")
            
            if not image_ref:
                self.toast_manager.warning("Нет ссылки на изображение в запросе")
                return
            
            context_item = None
            if self.right_panel:
                for item in self.right_panel.context_items:
                    if item.id == image_ref:
                        context_item = item
                        break
            
            if not context_item:
                self.toast_manager.warning(f"Не удается найти элемент контекста: {image_ref}")
                return
            
            await self._open_image_viewer(context_item, [action])
        
        except Exception as e:
            self.toast_manager.error(f"Ошибка обработки запроса области: {e}")
    
    async def _open_image_viewer(self: "MainWindow", context_item, model_actions: list):
        """Open image viewer dialog with ROI selection"""
        from app.ui.image_viewer import ImageViewerDialog
        
        if not self.r2_client:
            self.toast_manager.error("R2 клиент не инициализирован")
            return
        
        try:
            self.toast_manager.info("Загрузка файла...")
            url = self.r2_client.build_public_url(context_item.r2_key)
            cached_path = await self.r2_client.download_to_cache(url, context_item.id)
            
            self.toast_manager.info("Создание превью...")
            preview_image = self.pdf_renderer.render_preview(cached_path, page_num=0, dpi=150)
            
            dialog = ImageViewerDialog(self)
            dialog.load_image(preview_image)
            dialog.set_model_suggestions(model_actions)
            
            dialog.roiSelected.connect(
                lambda bbox, note: asyncio.create_task(
                    self._on_roi_selected(context_item, cached_path, bbox, note)
                )
            )
            dialog.roiRejected.connect(self._on_roi_rejected)
            
            dialog.exec()
        
        except Exception as e:
            self.toast_manager.error(f"Ошибка открытия просмотра изображения: {e}")
    
    async def _on_roi_selected(self: "MainWindow", context_item, pdf_path: Path, bbox_norm: tuple, user_note: str):
        """Handle ROI selection"""
        self.toast_manager.info("Обработка выделенной области...")
        
        try:
            self.toast_manager.info("Создание области в высоком разрешении...")
            roi_png_bytes = self.pdf_renderer.render_roi(
                pdf_path,
                bbox_norm,
                page_num=0,
                dpi=400
            )
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            roi_filename = f"roi_{timestamp}.png"
            r2_key = f"artifacts/{self.current_conversation_id}/{roi_filename}"
            
            if self.r2_client:
                self.toast_manager.info("Загрузка области в R2...")
                await self.r2_client.upload_bytes(
                    r2_key,
                    roi_png_bytes,
                    content_type="image/png"
                )
                
                if self.supabase_repo and self.current_conversation_id:
                    await self.supabase_repo.qa_add_artifact(
                        conversation_id=str(self.current_conversation_id),
                        artifact_type="roi_png",
                        r2_key=r2_key,
                        file_name=roi_filename,
                        mime_type="image/png",
                        file_size=len(roi_png_bytes),
                        metadata={
                            "bbox_norm": list(bbox_norm),
                            "user_note": user_note,
                            "source_context_item_id": context_item.id,
                        }
                    )
            
            if self.gemini_client:
                self.toast_manager.info("Загрузка области в Gemini Files...")
                
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(roi_png_bytes)
                    tmp_path = Path(tmp.name)
                
                try:
                    result = await self.gemini_client.upload_file(
                        tmp_path,
                        mime_type="image/png",
                        display_name=f"Область: {roi_filename}"
                    )
                    
                    gemini_uri = result["uri"]
                    
                    roi_context = f"Пользователь выделил область на документе. Примечание: {user_note or 'нет'}"
                    
                    if self.chat_panel:
                        self.chat_panel.add_system_message(
                            f"ROI выделен и загружен. Отправка модели...",
                            "success"
                        )
                        self.chat_panel.set_input_enabled(False)
                    
                    file_refs = []
                    for gf in self.attached_gemini_files:
                        file_refs.append({
                            "uri": gf["gemini_uri"],
                            "mime_type": gf.get("mime_type", "application/pdf"),
                        })
                    
                    file_refs.append({
                        "uri": gemini_uri,
                        "mime_type": "image/png",
                    })
                    
                    current_model = self.chat_panel.model_combo.currentData() if self.chat_panel else None
                    if not current_model:
                        current_model = "gemini-2.5-flash"
                    
                    reply = await self.agent.ask(
                        conversation_id=self.current_conversation_id,
                        user_text=roi_context,
                        file_refs=file_refs,
                        model=current_model,
                    )
                    
                    if self.chat_panel:
                        meta = {
                            "model": current_model,
                            "thinking_level": "low",
                            "is_final": reply.is_final,
                            "actions": [
                                {"type": a.type, "payload": a.payload, "note": a.note}
                                for a in reply.actions
                            ]
                        }
                        self.chat_panel.add_assistant_message(reply.assistant_text, meta)
                        self.chat_panel.set_input_enabled(True)
                    
                    self.toast_manager.success("Область обработана успешно")
                
                finally:
                    if tmp_path.exists():
                        tmp_path.unlink()
        
        except Exception as e:
            self.toast_manager.error(f"Ошибка обработки области: {e}")
            if self.chat_panel:
                self.chat_panel.set_input_enabled(True)
    
    def _on_roi_rejected(self: "MainWindow", reason: str):
        """Handle ROI rejection"""
        self.toast_manager.info(f"Область отклонена: {reason}")
