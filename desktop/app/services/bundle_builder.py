"""Document bundle builder for Gemini context"""

import json
import logging
import re
from typing import Optional
from app.models.schemas import NodeFile, FileType

logger = logging.getLogger(__name__)

MAX_BUNDLE_CHARS = 300_000


class DocumentBundleBuilder:
    """Builds text bundles from node files for Gemini context"""

    # Priority order for text sources
    TEXT_SOURCE_PRIORITY = [FileType.OCR_HTML, FileType.RESULT_JSON, FileType.PDF]

    def select_primary_text_source(self, node_files: list[NodeFile]) -> Optional[NodeFile]:
        """
        Select best text source from node files.
        Priority: ocr_html -> result_json -> pdf
        """
        files_by_type = {nf.file_type: nf for nf in node_files}

        for file_type in self.TEXT_SOURCE_PRIORITY:
            if file_type.value in files_by_type:
                return files_by_type[file_type.value]

        return None

    def build_bundle_text(self, file_bytes: bytes, file_type: str) -> str:
        """
        Convert file bytes to plain text based on file type.
        Returns cleaned text truncated to MAX_BUNDLE_CHARS.
        """
        try:
            if file_type == FileType.OCR_HTML.value:
                return self._convert_html_to_text(file_bytes)
            elif file_type == FileType.RESULT_JSON.value:
                return self._extract_text_from_result_json(file_bytes)
            elif file_type == FileType.PDF.value:
                return "(PDF содержимое недоступно в текстовом виде)"
            else:
                # Try decode as text
                return file_bytes.decode("utf-8", errors="replace")[:MAX_BUNDLE_CHARS]
        except Exception as e:
            logger.error(f"Error building bundle text: {e}")
            return f"(Ошибка обработки файла: {e})"

    def _convert_html_to_text(self, html_bytes: bytes) -> str:
        """Convert HTML to plain text, removing tags and extra whitespace"""
        html_content = html_bytes.decode("utf-8", errors="replace")

        # Remove script and style tags with content
        html_content = re.sub(
            r"<script[^>]*>.*?</script>", "", html_content, flags=re.DOTALL | re.IGNORECASE
        )
        html_content = re.sub(
            r"<style[^>]*>.*?</style>", "", html_content, flags=re.DOTALL | re.IGNORECASE
        )

        # Remove HTML comments
        html_content = re.sub(r"<!--.*?-->", "", html_content, flags=re.DOTALL)

        # Replace common block tags with newlines
        block_tags = r"</?(p|div|br|h[1-6]|li|tr|td|th|table|thead|tbody)[^>]*>"
        html_content = re.sub(block_tags, "\n", html_content, flags=re.IGNORECASE)

        # Remove all remaining tags
        html_content = re.sub(r"<[^>]+>", "", html_content)

        # Decode HTML entities
        html_content = self._decode_html_entities(html_content)

        # Normalize whitespace
        html_content = re.sub(r"[ \t]+", " ", html_content)
        html_content = re.sub(r"\n\s*\n+", "\n\n", html_content)
        html_content = html_content.strip()

        return html_content[:MAX_BUNDLE_CHARS]

    def _decode_html_entities(self, text: str) -> str:
        """Decode common HTML entities"""
        entities = {
            "&amp;": "&",
            "&lt;": "<",
            "&gt;": ">",
            "&quot;": '"',
            "&apos;": "'",
            "&nbsp;": " ",
            "&#39;": "'",
            "&#x27;": "'",
        }
        for entity, char in entities.items():
            text = text.replace(entity, char)
        # Decode numeric entities
        text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
        text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), text)
        return text

    def _extract_text_from_result_json(self, json_bytes: bytes) -> str:
        """Extract useful text fields from result JSON"""
        try:
            data = json.loads(json_bytes.decode("utf-8"))
        except json.JSONDecodeError as e:
            return f"(Ошибка парсинга JSON: {e})"

        text_parts = []

        # Extract common text fields
        text_fields = ["text", "content", "body", "description", "summary", "title"]
        self._extract_fields(data, text_fields, text_parts)

        result = "\n\n".join(text_parts)
        return result[:MAX_BUNDLE_CHARS]

    def _extract_fields(self, obj, field_names: list[str], results: list[str], depth: int = 0):
        """Recursively extract text fields from JSON object"""
        if depth > 5:  # Limit recursion
            return

        if isinstance(obj, dict):
            for key, value in obj.items():
                if key.lower() in field_names and isinstance(value, str) and value.strip():
                    results.append(value.strip())
                elif isinstance(value, (dict, list)):
                    self._extract_fields(value, field_names, results, depth + 1)
        elif isinstance(obj, list):
            for item in obj[:50]:  # Limit array traversal
                self._extract_fields(item, field_names, results, depth + 1)

    def build_crop_index(self, crop_node_files: list[NodeFile]) -> list[dict]:
        """
        Build compact crop index from crop files.
        Extracts crop_id from file_name or r2_key.
        """
        crops = []

        for nf in crop_node_files:
            if nf.file_type != FileType.CROP.value:
                continue

            crop_id = self._extract_crop_id(nf.file_name, nf.r2_key)
            if crop_id:
                crops.append(
                    {
                        "crop_id": crop_id,
                        "context_item_id": str(nf.id),
                        "r2_key": nf.r2_key,
                    }
                )

        return crops

    def _extract_crop_id(self, file_name: str, r2_key: str) -> Optional[str]:
        """Extract crop ID from file name or r2_key"""
        # Try from r2_key: ".../crops/<ID>.pdf" or ".../crops/<ID>.png"
        match = re.search(r"/crops/([^/]+)\.[^.]+$", r2_key)
        if match:
            return match.group(1)

        # Try from file_name
        match = re.search(r"^([^.]+)\.[^.]+$", file_name)
        if match:
            return match.group(1)

        # Fallback: use file_name without extension
        if "." in file_name:
            return file_name.rsplit(".", 1)[0]

        return file_name or None

    def build_bundle(
        self,
        text_file_bytes: Optional[bytes],
        text_file_type: Optional[str],
        crop_node_files: list[NodeFile],
        document_name: str = "document",
    ) -> tuple[bytes, list[dict]]:
        """
        Build complete bundle.

        Returns:
            tuple of (bundle_text_bytes, crop_index_list)
        """
        parts = []

        # Header
        parts.append(f"=== ДОКУМЕНТ: {document_name} ===\n")

        # Text content
        if text_file_bytes and text_file_type:
            text_content = self.build_bundle_text(text_file_bytes, text_file_type)
            parts.append("--- ТЕКСТ ДОКУМЕНТА ---\n")
            parts.append(text_content)
            parts.append("\n")
        else:
            parts.append("(Текстовое содержимое недоступно)\n")

        # Crop index
        crop_index = self.build_crop_index(crop_node_files)

        if crop_index:
            parts.append("\n--- CROPS (изображения для детального анализа) ---\n")
            for crop in crop_index:
                parts.append(f"  - {crop['crop_id']}: context_item_id={crop['context_item_id']}\n")

        bundle_text = "".join(parts)

        # Enforce max size
        if len(bundle_text) > MAX_BUNDLE_CHARS:
            bundle_text = bundle_text[:MAX_BUNDLE_CHARS] + "\n... (обрезано)"

        return bundle_text.encode("utf-8"), crop_index

    def format_crop_index_section(self, crop_index: list[dict]) -> str:
        """Format crop index as text section for bundle"""
        if not crop_index:
            return ""

        lines = ["CROPS:"]
        for crop in crop_index:
            lines.append(f"  {crop['crop_id']}")
        return "\n".join(lines)
