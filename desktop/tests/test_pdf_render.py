"""Test PDFRenderer"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from app.services.pdf_render import PDFRenderer


@pytest.fixture
def renderer():
    """Create PDFRenderer"""
    return PDFRenderer()


@pytest.fixture
def mock_fitz():
    """Mock fitz (PyMuPDF)"""
    with patch("app.services.pdf_render.fitz") as mock:
        yield mock


class TestPDFRenderer:
    def test_init(self, renderer):
        """Test renderer initialization"""
        assert renderer is not None
    
    def test_render_preview_bytes(self, renderer, mock_fitz, tmp_path):
        """Test rendering preview to bytes"""
        # Create mock PDF
        mock_doc = Mock()
        mock_page = Mock()
        mock_pix = Mock()
        
        mock_pix.tobytes.return_value = b"PNG_DATA"
        mock_page.get_pixmap.return_value = mock_pix
        mock_page.rect = Mock(width=595, height=842)
        mock_doc.__getitem__.return_value = mock_page
        mock_doc.__len__.return_value = 1
        
        mock_fitz.open.return_value = mock_doc
        mock_fitz.Matrix = Mock(return_value=Mock())
        
        pdf_path = tmp_path / "test.pdf"
        result = renderer.render_preview_bytes(pdf_path, page_num=0, dpi=150)
        
        assert result == b"PNG_DATA"
        mock_page.get_pixmap.assert_called_once()
        mock_doc.close.assert_called_once()
    
    def test_render_roi(self, renderer, mock_fitz, tmp_path):
        """Test rendering ROI with clip"""
        # Create mock PDF
        mock_doc = Mock()
        mock_page = Mock()
        mock_pix = Mock()
        
        mock_pix.tobytes.return_value = b"ROI_PNG_DATA"
        mock_page.get_pixmap.return_value = mock_pix
        mock_page.rect = Mock(width=595, height=842)
        mock_doc.__getitem__.return_value = mock_page
        mock_doc.__len__.return_value = 1
        
        mock_fitz.open.return_value = mock_doc
        mock_fitz.Matrix = Mock(return_value=Mock())
        mock_fitz.Rect = Mock(return_value=Mock())
        
        pdf_path = tmp_path / "test.pdf"
        bbox_norm = (0.1, 0.1, 0.9, 0.9)
        
        result = renderer.render_roi(pdf_path, bbox_norm, page_num=0, dpi=400)
        
        assert result == b"ROI_PNG_DATA"
        
        # Verify clip was used
        call_kwargs = mock_page.get_pixmap.call_args[1]
        assert "clip" in call_kwargs
        
        mock_doc.close.assert_called_once()
    
    def test_get_page_count(self, renderer, mock_fitz, tmp_path):
        """Test getting page count"""
        mock_doc = Mock()
        mock_doc.__len__.return_value = 5
        mock_fitz.open.return_value = mock_doc
        
        pdf_path = tmp_path / "test.pdf"
        count = renderer.get_page_count(pdf_path)
        
        assert count == 5
        mock_doc.close.assert_called_once()
    
    def test_get_page_size(self, renderer, mock_fitz, tmp_path):
        """Test getting page size"""
        mock_doc = Mock()
        mock_page = Mock()
        mock_page.rect = Mock(width=595, height=842)
        mock_doc.__getitem__.return_value = mock_page
        mock_doc.__len__.return_value = 1
        mock_fitz.open.return_value = mock_doc
        
        pdf_path = tmp_path / "test.pdf"
        width, height = renderer.get_page_size(pdf_path, page_num=0)
        
        assert width == 595
        assert height == 842
        mock_doc.close.assert_called_once()
    
    def test_render_preview_invalid_page(self, renderer, mock_fitz, tmp_path):
        """Test render with invalid page number falls back to page 0"""
        mock_doc = Mock()
        mock_page = Mock()
        mock_pix = Mock()
        
        mock_pix.tobytes.return_value = b"PNG_DATA"
        mock_page.get_pixmap.return_value = mock_pix
        mock_page.rect = Mock(width=595, height=842)
        mock_doc.__getitem__.return_value = mock_page
        mock_doc.__len__.return_value = 1
        
        mock_fitz.open.return_value = mock_doc
        mock_fitz.Matrix = Mock(return_value=Mock())
        
        pdf_path = tmp_path / "test.pdf"
        
        # Request page 10 when only 1 page exists
        result = renderer.render_preview_bytes(pdf_path, page_num=10, dpi=150)
        
        # Should fall back to page 0
        assert result == b"PNG_DATA"
