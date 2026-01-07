"""
Миксин для настройки меню и тулбара
По образцу архитектуры из test/menu_setup.py
"""

from typing import TYPE_CHECKING

from PySide6.QtGui import QAction

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow


# Общие стили для меню (темная тема)
MENU_STYLE = """
    QMenuBar {
        background-color: #1e1e1e;
        color: #cccccc;
        border-bottom: 1px solid #3e3e42;
        padding: 2px 0px;
    }
    QMenuBar::item {
        background-color: transparent;
        padding: 6px 12px;
        margin: 0px;
    }
    QMenuBar::item:selected {
        background-color: #094771;
        color: #ffffff;
    }
    QMenuBar::item:pressed {
        background-color: #0e639c;
    }
    QMenu {
        background-color: #252526;
        color: #cccccc;
        border: 1px solid #3e3e42;
        padding: 4px 0px;
    }
    QMenu::item {
        padding: 8px 32px 8px 12px;
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
    QMenu::icon {
        margin-left: 8px;
    }
"""

# Стили для контекстного меню
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


class MenuSetupMixin:
    """Миксин для создания меню и тулбара"""

    def _setup_menu(self: "MainWindow"):
        """Настройка главного меню"""
        menubar = self.menuBar()
        menubar.setStyleSheet(MENU_STYLE)

        self._setup_file_menu(menubar)
        self._setup_view_menu(menubar)
        self._setup_settings_menu(menubar)

    def _setup_file_menu(self: "MainWindow", menubar):
        """Настройка меню 'Файл'"""
        file_menu = menubar.addMenu("📁 Файл")

        self.action_upload = QAction("📤  Загрузить в Gemini", self)
        self.action_upload.setShortcut("Ctrl+U")
        self.action_upload.setToolTip("Загрузить выбранные файлы в Gemini Files")
        self.action_upload.triggered.connect(self._on_upload_selected)
        self.action_upload.setEnabled(False)
        file_menu.addAction(self.action_upload)

        file_menu.addSeparator()

        action_exit = QAction("🚪  Выход", self)
        action_exit.setShortcut("Alt+F4")
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

    def _setup_view_menu(self: "MainWindow", menubar):
        """Настройка меню 'Вид'"""
        view_menu = menubar.addMenu("👁 Вид")

        self.action_refresh_tree = QAction("🔄  Обновить дерево проектов", self)
        self.action_refresh_tree.setShortcut("Ctrl+R")
        self.action_refresh_tree.setToolTip("Обновить дерево проектов")
        self.action_refresh_tree.triggered.connect(self._on_refresh_tree)
        self.action_refresh_tree.setEnabled(False)
        view_menu.addAction(self.action_refresh_tree)

        self.action_refresh_gemini = QAction("🔄  Обновить Gemini Files", self)
        self.action_refresh_gemini.setShortcut("Ctrl+Shift+R")
        self.action_refresh_gemini.setToolTip("Обновить список Gemini Files")
        self.action_refresh_gemini.triggered.connect(self._on_refresh_gemini)
        self.action_refresh_gemini.setEnabled(False)
        view_menu.addAction(self.action_refresh_gemini)

        view_menu.addSeparator()

        self.action_model_inspector = QAction("🔍  Инспектор модели", self)
        self.action_model_inspector.setShortcut("Ctrl+I")
        self.action_model_inspector.setToolTip(
            "Открыть инспектор модели с полными логами, мыслями и токенами"
        )
        self.action_model_inspector.triggered.connect(self._on_open_inspector)
        view_menu.addAction(self.action_model_inspector)

        view_menu.addSeparator()

        # Подменю "Панели"
        panels_menu = view_menu.addMenu("📋  Панели")

        self.action_toggle_left = QAction("📂  Панель проектов", self)
        self.action_toggle_left.setCheckable(True)
        self.action_toggle_left.setChecked(True)
        self.action_toggle_left.setShortcut("Ctrl+1")
        self.action_toggle_left.triggered.connect(self._toggle_left_panel)
        panels_menu.addAction(self.action_toggle_left)

        self.action_toggle_right = QAction("📎  Панель контекста", self)
        self.action_toggle_right.setCheckable(True)
        self.action_toggle_right.setChecked(True)
        self.action_toggle_right.setShortcut("Ctrl+2")
        self.action_toggle_right.triggered.connect(self._toggle_right_panel)
        panels_menu.addAction(self.action_toggle_right)

    def _setup_settings_menu(self: "MainWindow", menubar):
        """Настройка меню 'Настройки'"""
        settings_menu = menubar.addMenu("⚙️ Настройки")

        self.action_settings = QAction("🔌  Настройки подключения", self)
        self.action_settings.setShortcut("Ctrl+,")
        self.action_settings.setToolTip("Настройки подключения")
        self.action_settings.triggered.connect(self._on_open_settings)
        settings_menu.addAction(self.action_settings)

        settings_menu.addSeparator()

        self.action_prompts = QAction("📝  Промты", self)
        self.action_prompts.setShortcut("Ctrl+P")
        self.action_prompts.setToolTip("Управление промтами")
        self.action_prompts.triggered.connect(self._on_open_prompts)
        self.action_prompts.setEnabled(False)
        settings_menu.addAction(self.action_prompts)
