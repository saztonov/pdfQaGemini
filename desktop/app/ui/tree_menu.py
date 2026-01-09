"""
Миксин для контекстного меню дерева проектов
По образцу архитектуры из test/menu_setup.py
"""

import asyncio
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu

if TYPE_CHECKING:
    from app.ui.left_projects_panel import LeftProjectsPanel

# Стили для контекстного меню (темная тема)
CONTEXT_MENU_STYLE = """
    QMenu {
        background-color: #252526;
        color: #cccccc;
        border: 1px solid #3e3e42;
        padding: 4px 0px;
    }
    QMenu::item {
        padding: 8px 24px 8px 12px;
        margin: 0px;
    }
    QMenu::item:selected {
        background-color: #094771;
        color: #ffffff;
    }
    QMenu::separator {
        height: 1px;
        background-color: #3e3e42;
        margin: 4px 8px;
    }
"""


class TreeContextMenuMixin:
    """Миксин для контекстного меню дерева проектов"""

    def _show_context_menu(self: "LeftProjectsPanel", position):
        """Показать контекстное меню для элементов дерева"""
        item = self.tree.itemAt(position)
        if not item:
            return

        menu = QMenu(self.tree)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)

        # Определяем тип элемента
        item_type = item.data(0, Qt.UserRole + 3)
        node_id = item.data(0, Qt.UserRole)

        # Проверяем, можно ли добавить элемент в Gemini
        can_add = self._can_add_to_gemini(item_type, node_id)

        if can_add:
            self._add_gemini_action(menu, item_type)

        # Добавляем действие скачивания
        self._add_download_action(menu)

        if not menu.isEmpty():
            menu.exec_(self.tree.viewport().mapToGlobal(position))

    def _can_add_to_gemini(self: "LeftProjectsPanel", item_type: str, node_id: str) -> bool:
        """Проверка возможности добавления в Gemini"""
        if item_type in ("file", "crops_folder"):
            return True

        if item_type not in ("file", "crops_folder", "files_folder") and node_id:
            try:
                from uuid import UUID

                UUID(node_id)
                return True
            except (ValueError, TypeError):
                pass

        return False

    def _add_gemini_action(self: "LeftProjectsPanel", menu: QMenu, item_type: str):
        """Добавить действие 'Добавить в Gemini Files'"""
        if item_type == "crops_folder":
            action_add = menu.addAction("📤  Добавить все кропы в Gemini Files")
        else:
            action_add = menu.addAction("📤  Добавить в Gemini Files")

        action_add.triggered.connect(lambda: asyncio.create_task(self.add_selected_to_context()))

    def _add_download_action(self: "LeftProjectsPanel", menu: QMenu):
        """Добавить действие 'Скачать документы'"""
        action_download = menu.addAction("📥  Скачать документы")
        action_download.triggered.connect(
            lambda: asyncio.create_task(self.download_selected_documents())
        )
