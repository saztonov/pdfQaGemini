"""Tree download operations - download files from R2 to Downloads folder"""
import asyncio
import logging
import os
import platform
import subprocess
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from app.ui.left_projects_panel import LeftProjectsPanel

logger = logging.getLogger(__name__)


def get_downloads_folder() -> Path:
    """Get user's Downloads folder path"""
    if platform.system() == "Windows":
        import winreg
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            ) as key:
                downloads = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")[0]
                return Path(downloads)
        except Exception:
            pass
    return Path.home() / "Downloads"


def open_folder(path: Path):
    """Open folder in file explorer"""
    try:
        if platform.system() == "Windows":
            os.startfile(str(path))
        elif platform.system() == "Darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception as e:
        logger.error(f"Failed to open folder: {e}")


class TreeDownloadMixin:
    """Mixin for downloading files from tree"""

    async def download_selected_documents(self: "LeftProjectsPanel"):
        """Download selected documents to Downloads folder"""
        from uuid import UUID

        if not self.r2_client:
            if self.toast_manager:
                self.toast_manager.error("R2 клиент не инициализирован")
            return

        selected_items = self.tree.selectedItems()
        if not selected_items:
            if self.toast_manager:
                self.toast_manager.warning("Нет выбранных элементов")
            return

        # Collect all files to download
        files_to_download: list[dict] = []

        for item in selected_items:
            await self._collect_files_for_download(item, files_to_download)

        if not files_to_download:
            if self.toast_manager:
                self.toast_manager.warning("Нет файлов для скачивания")
            return

        # Download files
        downloads_folder = get_downloads_folder()
        downloads_folder.mkdir(parents=True, exist_ok=True)

        if self.toast_manager:
            self.toast_manager.info(f"Скачивание {len(files_to_download)} файлов...")

        try:
            downloaded_files: list[Path] = []

            for file_info in files_to_download:
                r2_key = file_info["r2_key"]
                file_name = file_info["file_name"]

                try:
                    # Download from R2
                    data = await self.r2_client.download_bytes(r2_key)

                    # Save to temp location
                    temp_path = downloads_folder / file_name

                    # Handle duplicate names
                    counter = 1
                    original_stem = temp_path.stem
                    original_suffix = temp_path.suffix
                    while temp_path.exists():
                        temp_path = downloads_folder / f"{original_stem}_{counter}{original_suffix}"
                        counter += 1

                    temp_path.write_bytes(data)
                    downloaded_files.append(temp_path)
                    logger.info(f"Downloaded: {file_name} -> {temp_path}")

                except Exception as e:
                    logger.error(f"Failed to download {file_name}: {e}")

            if not downloaded_files:
                if self.toast_manager:
                    self.toast_manager.error("Не удалось скачать файлы")
                return

            # If multiple files - create zip archive
            if len(downloaded_files) > 1:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                zip_name = f"documents_{timestamp}.zip"
                zip_path = downloads_folder / zip_name

                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for file_path in downloaded_files:
                        zf.write(file_path, file_path.name)

                # Remove individual files after zipping
                for file_path in downloaded_files:
                    try:
                        file_path.unlink()
                    except Exception:
                        pass

                final_path = zip_path
                message = f"Скачан архив: {zip_name}"
            else:
                final_path = downloaded_files[0]
                message = f"Скачан файл: {final_path.name}"

            if self.toast_manager:
                self.toast_manager.success(message)

            # Open folder
            open_folder(downloads_folder)

        except Exception as e:
            logger.error(f"Download error: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка скачивания: {e}")

    async def _collect_files_for_download(
        self: "LeftProjectsPanel",
        item,
        files_list: list[dict]
    ):
        """Recursively collect files from tree item"""
        from uuid import UUID

        item_type = item.data(0, Qt.UserRole + 3)
        node_id = item.data(0, Qt.UserRole)

        # If it's a file - add directly
        if item_type == "file":
            file_info = self._extract_download_file_info(item)
            if file_info and file_info not in files_list:
                files_list.append(file_info)
            return

        # If it's a folder with files (crops_folder, files_folder)
        if item_type in ("crops_folder", "files_folder"):
            for i in range(item.childCount()):
                child = item.child(i)
                await self._collect_files_for_download(child, files_list)
            return

        # If it's a tree node (project, section, document, etc.)
        if node_id:
            try:
                UUID(node_id)
            except (ValueError, TypeError):
                return

            # Check if children are loaded
            if item.childCount() > 0:
                first_child = item.child(0)
                # If placeholder exists, need to load children
                if first_child.data(0, Qt.UserRole) is None:
                    await self._load_children(item, node_id)

            # Get node type
            node_type = item.data(0, Qt.UserRole + 1)

            # If document - collect its files
            if node_type == "document":
                for i in range(item.childCount()):
                    child = item.child(i)
                    await self._collect_files_for_download(child, files_list)
            else:
                # For folders - recursively process children
                for i in range(item.childCount()):
                    child = item.child(i)
                    await self._collect_files_for_download(child, files_list)

    def _extract_download_file_info(self: "LeftProjectsPanel", item) -> dict | None:
        """Extract file info for download"""
        file_id = item.data(0, Qt.UserRole)
        r2_key = item.data(0, Qt.UserRole + 4)

        if not file_id or not r2_key:
            return None

        # Extract file name from item text (remove icon)
        file_name = item.text(0)
        for icon in ["📄", "📋", "📝", "📊", "🖼️"]:
            file_name = file_name.replace(icon, "").strip()

        return {
            "id": file_id,
            "r2_key": r2_key,
            "file_name": file_name,
        }
