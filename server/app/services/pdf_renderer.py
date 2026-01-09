"""PDF rendering utilities for server-side ROI extraction.

Uses PyMuPDF (fitz) for PDF rendering without Qt dependencies.
"""

import fitz  # PyMuPDF
import logging
from pathlib import Path
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class PDFRenderer:
    """Render PDF pages to images with ROI support (server-side)"""

    def render_roi(
        self,
        pdf_data: bytes,
        bbox_norm: Tuple[float, float, float, float],
        page_num: int = 0,
        dpi: int = 400,
    ) -> bytes:
        """
        Render ROI (Region of Interest) at high resolution.

        Args:
            pdf_data: PDF file content as bytes
            bbox_norm: Normalized bounding box (x1, y1, x2, y2) in range [0, 1]
            page_num: Page number (0-indexed)
            dpi: Resolution for output (default 400)

        Returns:
            PNG bytes of cropped region
        """
        doc = fitz.open(stream=pdf_data, filetype="pdf")

        try:
            if page_num >= len(doc):
                page_num = 0

            page = doc[page_num]

            # Get page dimensions
            page_rect = page.rect
            page_width = page_rect.width
            page_height = page_rect.height

            # Convert normalized bbox to page coordinates
            x1_norm, y1_norm, x2_norm, y2_norm = bbox_norm
            x1 = x1_norm * page_width
            y1 = y1_norm * page_height
            x2 = x2_norm * page_width
            y2 = y2_norm * page_height

            # Create clip rectangle
            clip_rect = fitz.Rect(x1, y1, x2, y2)

            # Calculate zoom factor (PyMuPDF default is 72 DPI)
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)

            # Render only the clipped region
            pix = page.get_pixmap(matrix=mat, clip=clip_rect, alpha=False)

            png_bytes = pix.tobytes("png")

            logger.info(
                f"Rendered ROI: bbox={bbox_norm}, page={page_num}, "
                f"dpi={dpi}, size={pix.width}x{pix.height}, bytes={len(png_bytes)}"
            )

            return png_bytes

        finally:
            doc.close()

    def render_page(
        self,
        pdf_data: bytes,
        page_num: int = 0,
        dpi: int = 150,
    ) -> bytes:
        """
        Render full page as PNG.

        Args:
            pdf_data: PDF file content as bytes
            page_num: Page number (0-indexed)
            dpi: Resolution (default 150)

        Returns:
            PNG bytes of rendered page
        """
        doc = fitz.open(stream=pdf_data, filetype="pdf")

        try:
            if page_num >= len(doc):
                page_num = 0

            page = doc[page_num]

            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)

            pix = page.get_pixmap(matrix=mat, alpha=False)
            png_bytes = pix.tobytes("png")

            return png_bytes

        finally:
            doc.close()

    def get_page_count(self, pdf_data: bytes) -> int:
        """Get number of pages in PDF"""
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        try:
            return len(doc)
        finally:
            doc.close()

    def get_page_size(self, pdf_data: bytes, page_num: int = 0) -> Tuple[float, float]:
        """Get page dimensions in points"""
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        try:
            if page_num >= len(doc):
                page_num = 0
            page = doc[page_num]
            rect = page.rect
            return (rect.width, rect.height)
        finally:
            doc.close()
