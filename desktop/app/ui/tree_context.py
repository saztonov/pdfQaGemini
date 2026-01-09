"""Tree context operations (add to context)"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.ui.left_projects_panel import LeftProjectsPanel

logger = logging.getLogger(__name__)


class TreeContextMixin:
    """Mixin for tree context operations"""

    async def add_selected_to_context(self: "LeftProjectsPanel"):
        """Add selected nodes to context (with descendants)"""
        if self._adding_to_context:
            logger.info("add_selected_to_context уже выполняется, пропуск")
            return

        self._adding_to_context = True
        try:
            await self._add_selected_to_context_impl()
        finally:
            self._adding_to_context = False

    async def _add_selected_to_context_impl(self: "LeftProjectsPanel"):
        """Internal implementation"""
        from PySide6.QtCore import Qt
        from uuid import UUID

        logger.info("=== ДОБАВЛЕНИЕ В КОНТЕКСТ ===")
        logger.info(f"self.supabase_repo: {self.supabase_repo is not None}")

        if not self.supabase_repo:
            logger.error("ОШИБКА: Репозиторий не инициализирован")
            if self.toast_manager:
                self.toast_manager.error("Репозиторий не инициализирован")
            return

        selected_items = self.tree.selectedItems()
        if not selected_items:
            if self.toast_manager:
                self.toast_manager.warning("Нет выбранных узлов")
            return

        selected_node_ids = []
        selected_files_info = []

        for item in selected_items:
            item_type = item.data(0, Qt.UserRole + 3)

            # Handle files
            if item_type == "file":
                file_info = self._extract_file_info(item)
                if file_info:
                    selected_files_info.append(file_info)
                continue

            # Handle crops_folder - collect all crop files inside
            if item_type == "crops_folder":
                crops_count = 0
                for i in range(item.childCount()):
                    child = item.child(i)
                    child_type = child.data(0, Qt.UserRole + 3)

                    if child_type == "file":
                        file_info = self._extract_file_info_from_crop(child, item)
                        if file_info:
                            selected_files_info.append(file_info)
                            crops_count += 1
                logger.info(f"Выбрана папка кропов, добавлено {crops_count} файлов")
                continue

            # Handle regular nodes
            node_id = item.data(0, Qt.UserRole)
            if node_id:
                try:
                    UUID(node_id)
                    selected_node_ids.append(node_id)
                except (ValueError, TypeError):
                    continue

        # Emit files signal if any files selected
        if selected_files_info:
            logger.info(f"Emit addFilesToContextRequested с {len(selected_files_info)} файлами")
            self.addFilesToContextRequested.emit(selected_files_info)

        # Process nodes if any nodes selected
        if not selected_node_ids:
            if not selected_files_info:
                if self.toast_manager:
                    self.toast_manager.warning("Выберите проекты/разделы/документы или файлы")
            return

        logger.info(f"Выбрано узлов: {len(selected_node_ids)}, IDs: {selected_node_ids}")

        if self.toast_manager:
            self.toast_manager.info(f"Поиск документов в {len(selected_node_ids)} узлах...")

        try:
            # Get client_id from first cached node
            client_id = None
            for nid in selected_node_ids:
                cached = self._node_cache.get(nid)
                if cached:
                    logger.info(
                        f"  Узел {nid}: type={cached.node_type}, name={cached.name}, client_id={cached.client_id}"
                    )
                    if not client_id:
                        client_id = cached.client_id

            if not client_id:
                logger.error("Не удалось определить client_id из кеша")
                if self.toast_manager:
                    self.toast_manager.error("Не удалось определить client_id")
                return

            # Get descendant documents
            logger.info(
                f"Вызов get_descendant_documents(client_id='{client_id}', root_ids={selected_node_ids})"
            )
            documents = await self.supabase_repo.get_descendant_documents(
                client_id, selected_node_ids, node_types=["document"]
            )

            logger.info(f"RPC вернул {len(documents)} документов")
            for doc in documents[:5]:
                logger.info(f"  doc: id={doc.id}, name={doc.name}, type={doc.node_type}")

            document_ids = [str(doc.id) for doc in documents]

            if not document_ids:
                logger.warning("Документы не найдены в RPC ответе")
                if self.toast_manager:
                    self.toast_manager.warning("Документы не найдены")
                return

            # Emit signal
            logger.info(f"Emit addToContextRequested с {len(document_ids)} документами")
            self.addToContextRequested.emit(document_ids)

        except Exception as e:
            logger.error(f"Ошибка get_descendant_documents: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка: {e}")

    def _extract_file_info(self: "LeftProjectsPanel", item) -> dict | None:
        """Extract file info from tree item"""
        from PySide6.QtCore import Qt

        file_id = item.data(0, Qt.UserRole)
        r2_key = item.data(0, Qt.UserRole + 4)
        file_type = item.data(0, Qt.UserRole + 5)
        mime_type = item.data(0, Qt.UserRole + 6)

        if not file_id or not r2_key:
            return None

        # Get node_id from parent (should be document)
        parent_item = item.parent()
        node_id = None
        if parent_item:
            parent_type = parent_item.data(0, Qt.UserRole + 3)
            if parent_type == "crops_folder":
                doc_item = parent_item.parent()
                if doc_item:
                    node_id = doc_item.data(0, Qt.UserRole)
            else:
                node_id = parent_item.data(0, Qt.UserRole)

        # Extract file name from item text (remove icon)
        file_name = item.text(0)
        for icon in ["📄", "📋", "📝", "📊", "🖼️"]:
            file_name = file_name.replace(icon, "").strip()

        # Prefer DB mime_type, fallback to guessing
        if not mime_type:
            mime_type = self._get_fallback_mime_type(file_type, r2_key)

        return {
            "id": file_id,
            "r2_key": r2_key,
            "file_name": file_name,
            "file_type": file_type,
            "mime_type": mime_type,
            "node_id": node_id,
        }

    def _extract_file_info_from_crop(
        self: "LeftProjectsPanel", child, crops_folder_item
    ) -> dict | None:
        """Extract file info from crop item"""
        from PySide6.QtCore import Qt

        file_id = child.data(0, Qt.UserRole)
        r2_key = child.data(0, Qt.UserRole + 4)
        file_type = child.data(0, Qt.UserRole + 5)
        mime_type = child.data(0, Qt.UserRole + 6)

        if not file_id or not r2_key:
            return None

        # Get node_id from crops_folder parent (document)
        parent_item = crops_folder_item.parent()
        node_id = parent_item.data(0, Qt.UserRole) if parent_item else None

        file_name = child.text(0)
        for icon in ["📄", "📋", "📝", "📊", "🖼️"]:
            file_name = file_name.replace(icon, "").strip()

        # Prefer DB mime_type, fallback to guessing
        if not mime_type:
            mime_type = self._get_fallback_mime_type(file_type, r2_key)

        return {
            "id": file_id,
            "r2_key": r2_key,
            "file_name": file_name,
            "file_type": file_type,
            "mime_type": mime_type,
            "node_id": node_id,
        }

    def get_selected_node_ids(self: "LeftProjectsPanel") -> list[str]:
        """Get selected node IDs (only valid tree nodes, not files/folders)"""
        from uuid import UUID
        from PySide6.QtCore import Qt

        selected = []
        for item in self.tree.selectedItems():
            item_type = item.data(0, Qt.UserRole + 3)
            if item_type in ("file", "crops_folder", "files_folder"):
                continue
            node_id = item.data(0, Qt.UserRole)
            if node_id:
                try:
                    UUID(node_id)
                    selected.append(node_id)
                except (ValueError, TypeError):
                    continue
        return selected

    def _get_fallback_mime_type(self: "LeftProjectsPanel", file_type: str, r2_key: str) -> str:
        """Get fallback MIME type when DB mime_type is empty"""
        # Fallback by file_type
        if file_type == "pdf":
            return "application/pdf"
        if file_type == "ocr_html":
            return "text/plain"
        if file_type in ("annotation", "result_json"):
            return "application/json"
        if file_type == "crop":
            # Guess by extension
            ext = r2_key.rsplit(".", 1)[-1].lower() if "." in r2_key else ""
            if ext == "pdf":
                return "application/pdf"
            if ext in ("png", "jpg", "jpeg", "webp", "gif"):
                return f"image/{ext.replace('jpg', 'jpeg')}"
            return "application/pdf"
        return "application/octet-stream"
