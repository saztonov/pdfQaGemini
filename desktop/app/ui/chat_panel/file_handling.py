"""File handling for chat panel"""

from PySide6.QtCore import QUrl
from app.ui.chat_widgets import FileChip


class FileHandlingMixin:
    """Mixin for file chip handling in chat panel"""

    def _update_files_visibility(self):
        """Update files panel visibility"""
        has_files = len(self._available_files) > 0
        self.files_scroll.setVisible(has_files)
        self.no_files_label.setVisible(not has_files)

    def set_available_files(self, files: list[dict]):
        """Set available Gemini files for selection"""
        self._available_files = files
        self._rebuild_file_chips()
        self._update_files_visibility()

    def _rebuild_file_chips(self):
        """Rebuild file chips from available files"""
        # Clear existing chips
        while self.files_layout.count() > 1:  # Keep stretch
            item = self.files_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add chips for each file
        for file_info in self._available_files:
            name = file_info.get("name", "")
            display = file_info.get("display_name") or name
            selected = name in self._selected_files

            chip = FileChip(name, display, selected)
            chip.clicked.connect(self._on_file_chip_clicked)
            self.files_layout.insertWidget(self.files_layout.count() - 1, chip)

    def _on_file_chip_clicked(self, file_name: str, is_selected: bool):
        """Handle file chip click"""
        if is_selected:
            # Find file info
            for f in self._available_files:
                if f.get("name") == file_name:
                    self._selected_files[file_name] = f
                    break
        else:
            self._selected_files.pop(file_name, None)

    def _select_all_files(self):
        """Select all available files"""
        self._selected_files.clear()
        for f in self._available_files:
            name = f.get("name", "")
            if name:
                self._selected_files[name] = f
        self._rebuild_file_chips()

    def _clear_file_selection(self):
        """Clear file selection"""
        self._selected_files.clear()
        self._rebuild_file_chips()

    def add_selected_files(self, file_infos: list[dict]):
        """Auto-select files by name (for agentic crops loading)"""
        for f in file_infos:
            name = f.get("name", "")
            if not name:
                continue
            # Add to available if not present
            if not any(af.get("name") == name for af in self._available_files):
                self._available_files.append(f)
            # Select it
            self._selected_files[name] = f
        self._rebuild_file_chips()

    def get_selected_file_refs(self) -> list[dict]:
        """Get selected file references for request"""
        refs = []
        for f in self._selected_files.values():
            refs.append(
                {
                    "uri": f.get("uri"),
                    "mime_type": f.get("mime_type", "application/octet-stream"),
                    "display_name": f.get("display_name"),
                }
            )
        return refs

    def _on_link_clicked(self, url: QUrl):
        """Handle link clicks"""
        url_str = url.toString()
        # External links
        if url_str.startswith("http://") or url_str.startswith("https://"):
            from PySide6.QtGui import QDesktopServices

            QDesktopServices.openUrl(url)
