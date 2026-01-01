"""PDF rendering utilities using PyMuPDF"""
import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional, Tuple
from PySide6.QtGui import QImage


class PDFRenderer:
    """Render PDF pages to images with ROI support"""
    
    def __init__(self):
        pass
    
    def render_preview(
        self,
        pdf_path: Path,
        page_num: int = 0,
        dpi: int = 150
    ) -> QImage:
        """
        Render page preview for display.
        
        Args:
            pdf_path: Path to PDF file
            page_num: Page number (0-indexed)
            dpi: Resolution (default 150 for preview)
        
        Returns:
            QImage for display
        """
        doc = fitz.open(str(pdf_path))
        
        if page_num >= len(doc):
            page_num = 0
        
        page = doc[page_num]
        
        # Calculate zoom factor from DPI
        # PyMuPDF default is 72 DPI
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        
        # Render to pixmap
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # Convert to QImage
        img = QImage(
            pix.samples,
            pix.width,
            pix.height,
            pix.stride,
            QImage.Format_RGB888
        )
        
        doc.close()
        return img.copy()
    
    def render_preview_bytes(
        self,
        pdf_path: Path,
        page_num: int = 0,
        dpi: int = 150
    ) -> bytes:
        """Render page preview to PNG bytes"""
        doc = fitz.open(str(pdf_path))
        
        if page_num >= len(doc):
            page_num = 0
        
        page = doc[page_num]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        png_bytes = pix.tobytes("png")
        doc.close()
        return png_bytes
    
    def render_roi(
        self,
        pdf_path: Path,
        bbox_norm: Tuple[float, float, float, float],
        page_num: int = 0,
        dpi: int = 400
    ) -> bytes:
        """
        Render ROI (Region of Interest) with high quality using clip.
        
        Args:
            pdf_path: Path to PDF file
            bbox_norm: Normalized bounding box (x0, y0, x1, y1) in range [0, 1]
            page_num: Page number (0-indexed)
            dpi: High resolution for ROI (default 400)
        
        Returns:
            PNG bytes of cropped region
        """
        doc = fitz.open(str(pdf_path))
        
        if page_num >= len(doc):
            page_num = 0
        
        page = doc[page_num]
        
        # Get page dimensions
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height
        
        # Convert normalized bbox to page coordinates
        x0_norm, y0_norm, x1_norm, y1_norm = bbox_norm
        x0 = x0_norm * page_width
        y0 = y0_norm * page_height
        x1 = x1_norm * page_width
        y1 = y1_norm * page_height
        
        # Create clip rectangle
        clip_rect = fitz.Rect(x0, y0, x1, y1)
        
        # Calculate zoom factor
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        
        # Render only the clipped region (performance optimization)
        pix = page.get_pixmap(matrix=mat, clip=clip_rect, alpha=False)
        
        png_bytes = pix.tobytes("png")
        doc.close()
        return png_bytes
    
    def get_page_count(self, pdf_path: Path) -> int:
        """Get number of pages in PDF"""
        doc = fitz.open(str(pdf_path))
        count = len(doc)
        doc.close()
        return count
    
    def get_page_size(self, pdf_path: Path, page_num: int = 0) -> Tuple[float, float]:
        """Get page dimensions in points"""
        doc = fitz.open(str(pdf_path))
        
        if page_num >= len(doc):
            page_num = 0
        
        page = doc[page_num]
        rect = page.rect
        width = rect.width
        height = rect.height
        
        doc.close()
        return (width, height)
