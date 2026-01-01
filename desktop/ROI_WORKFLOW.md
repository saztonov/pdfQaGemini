# ROI Extraction Workflow

## Overview

ROI (Region of Interest) extraction позволяет пользователю выделить конкретную область документа для детального анализа моделью.

## Architecture

### Components

1. **PDFRenderer** (`app/services/pdf_render.py`)
   - `render_preview()`: быстрый preview (150 DPI)
   - `render_roi()`: высококачественный рендер ROI с clip (400 DPI)
   - Использует PyMuPDF (fitz) для рендеринга

2. **ROIGraphicsView** (`app/ui/image_viewer.py`)
   - QGraphicsView с pan/zoom
   - Режим выделения ROI прямоугольником
   - Emit `roiDrawn(QRectF)` с normalized координатами [0, 1]

3. **ImageViewerDialog** (`app/ui/image_viewer.py`)
   - ROIGraphicsView + sidebar
   - Список model suggestions
   - Note editor
   - Кнопки: Confirm ROI, Reject, Enable ROI Mode, Clear ROI, Fit to View
   - Signals: `roiSelected(bbox_norm, user_note)`, `roiRejected(reason)`

4. **MainWindow Integration** (`app/ui/main_window.py`)
   - `_handle_request_roi_action()`: обработка action от модели
   - `_open_image_viewer()`: download + render + open dialog
   - `_on_roi_selected()`: полный pipeline после выделения ROI

## Workflow

### 1. Model Request ROI

Модель возвращает action:
```json
{
  "type": "request_roi",
  "payload": {
    "image_ref": "context_item_id",
    "hint_text": "Выделите таблицу в верхней части страницы"
  },
  "note": "Нужна таблица с данными"
}
```

### 2. Open Image Viewer

```python
# MainWindow._handle_request_roi_action()
context_item = find_context_item(image_ref)
await _open_image_viewer(context_item, [action])
```

**Steps:**
1. Download PDF from R2 → cache
2. Render preview (150 DPI) → QImage
3. Create ImageViewerDialog
4. Load image, set model suggestions
5. Show dialog (non-blocking)

### 3. User Selects ROI

**User actions:**
1. Click "Enable ROI Selection"
2. Draw rectangle on image (mouse drag)
3. (Optional) Add note in text field
4. Click "Confirm ROI"

**Dialog emits:**
```python
roiSelected.emit(
    bbox_norm=(0.1, 0.2, 0.9, 0.8),  # (x0, y0, x1, y1) normalized
    user_note="Таблица с финансовыми данными"
)
```

### 4. Process ROI

```python
# MainWindow._on_roi_selected()
```

**Steps:**

#### 4.1. Render High-Quality ROI
```python
roi_png_bytes = pdf_renderer.render_roi(
    pdf_path=cached_pdf_path,
    bbox_norm=(0.1, 0.2, 0.9, 0.8),
    page_num=0,
    dpi=400  # High quality
)
```

**Performance optimization:**
- PyMuPDF `clip` parameter рендерит только выделенную область
- НЕ рендерим всю страницу в 400 DPI

#### 4.2. Upload to R2 (Artifact)
```python
r2_key = f"artifacts/{conversation_id}/roi_{timestamp}.png"
await r2_client.upload_bytes(r2_key, roi_png_bytes, "image/png")
```

#### 4.3. Save Artifact Metadata
```python
await supabase_repo.qa_add_artifact(
    conversation_id=conversation_id,
    artifact_type="roi_png",
    r2_key=r2_key,
    file_name="roi_20250101_120000.png",
    mime_type="image/png",
    file_size=len(roi_png_bytes),
    metadata={
        "bbox_norm": [0.1, 0.2, 0.9, 0.8],
        "user_note": "Таблица с финансовыми данными",
        "source_context_item_id": context_item.id
    }
)
```

#### 4.4. Upload to Gemini Files
```python
# Save to temp file
with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
    tmp.write(roi_png_bytes)
    tmp_path = Path(tmp.name)

result = await gemini_client.upload_file(
    tmp_path,
    mime_type="image/png",
    display_name=f"ROI: roi_{timestamp}.png"
)

gemini_uri = result["uri"]
```

#### 4.5. Ask Model Again with ROI
```python
roi_context = f"Пользователь выделил область на документе. Примечание: {user_note}"

# Include original files + ROI
file_uris = [gf["gemini_uri"] for gf in attached_gemini_files]
file_uris.append(gemini_uri)

reply = await agent.ask(
    conversation_id=conversation_id,
    user_text=roi_context,
    file_uris=file_uris
)

# Display assistant reply
chat_panel.add_assistant_message(reply.assistant_text, meta)
```

### 5. Model Analyzes ROI

Модель получает:
- Original document files
- **ROI image** (high-quality 400 DPI PNG)
- User context: "Пользователь выделил область на документе. Примечание: ..."

Модель может:
- Извлечь текст из ROI
- Распознать таблицу
- Ответить на вопросы по ROI
- Запросить дополнительные ROI если нужно

## Data Flow Diagram

```
User Question
    ↓
Agent.ask() → ModelReply
    ↓
Action: request_roi
    ↓
Download PDF from R2
    ↓
Render Preview (150 DPI)
    ↓
ImageViewerDialog
    ↓
User draws ROI rectangle
    ↓
roiSelected.emit(bbox_norm, note)
    ↓
Render ROI (400 DPI, clip)
    ↓
Upload to R2 (artifact)
    ↓
Save metadata (qa_artifacts)
    ↓
Upload to Gemini Files
    ↓
Agent.ask() with ROI file_uri
    ↓
Model analyzes ROI
    ↓
Display assistant reply
```

## Performance Optimizations

### 1. PyMuPDF Clip
```python
# BAD: Render full page at 400 DPI, then crop
pix = page.get_pixmap(matrix=mat_400dpi)
cropped = crop_pixmap(pix, bbox)  # Slow!

# GOOD: Render only ROI region
clip_rect = fitz.Rect(x0, y0, x1, y1)
pix = page.get_pixmap(matrix=mat_400dpi, clip=clip_rect)  # Fast!
```

### 2. DPI Levels
- Preview: 150 DPI (для быстрого отображения)
- ROI: 400 DPI (для высокого качества OCR/analysis)

### 3. Caching
- PDF downloaded once, cached locally
- Preview image не пересоздаётся при повторном открытии

### 4. Async Operations
- Все IO операции async (download, upload, render через to_thread)
- UI никогда не блокируется

### 5. Temp File Cleanup
```python
try:
    # Upload to Gemini
    result = await gemini_client.upload_file(tmp_path, ...)
finally:
    if tmp_path.exists():
        tmp_path.unlink()  # Clean up
```

## Error Handling

### User Cancels
```python
dialog.roiRejected.connect(self._on_roi_rejected)

def _on_roi_rejected(self, reason: str):
    self.toast_manager.info(f"ROI rejected: {reason}")
    # No further action needed
```

### Upload Failures
```python
try:
    await r2_client.upload_bytes(...)
except Exception as e:
    toast_manager.error(f"Upload failed: {e}")
    chat_panel.set_input_enabled(True)  # Re-enable input
```

### Render Errors
```python
try:
    roi_png_bytes = pdf_renderer.render_roi(...)
except Exception as e:
    toast_manager.error(f"Render failed: {e}")
    return  # Don't proceed
```

## Testing

### PDFRenderer Tests
```python
def test_render_roi(renderer, mock_fitz):
    bbox_norm = (0.1, 0.1, 0.9, 0.9)
    result = renderer.render_roi(pdf_path, bbox_norm, dpi=400)
    
    # Verify clip was used
    call_kwargs = mock_page.get_pixmap.call_args[1]
    assert "clip" in call_kwargs
```

### ImageViewerDialog Tests
```python
def test_roi_drawn_enables_confirm(dialog):
    dialog.load_image(image)
    rect = QRectF(0.1, 0.1, 0.8, 0.8)
    dialog._on_roi_drawn(rect)
    
    assert dialog.btn_confirm.isEnabled()
    assert dialog.current_bbox_norm is not None
```

## Future Enhancements

1. **Multi-page support**: page selector в ImageViewerDialog
2. **Multiple ROIs**: выделение нескольких областей за раз
3. **ROI history**: показать предыдущие ROI на preview
4. **Annotations**: text/arrow overlays на ROI
5. **Batch processing**: автоматический ROI extraction по model suggestions
6. **ROI templates**: сохранённые bbox для типовых документов
7. **OCR preview**: показать распознанный текст сразу в диалоге

## Database Schema

### qa_artifacts table
```sql
CREATE TABLE qa_artifacts (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES qa_conversations(id),
    artifact_type TEXT CHECK (artifact_type IN ('roi_png', 'export_json')),
    r2_key TEXT NOT NULL,
    file_name TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_size BIGINT,
    metadata JSONB DEFAULT '{}',  -- bbox_norm, user_note, source_context_item_id
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Querying Artifacts
```python
# Get all ROIs for conversation
artifacts = await supabase_repo.execute(
    """
    SELECT * FROM qa_artifacts
    WHERE conversation_id = $1 AND artifact_type = 'roi_png'
    ORDER BY created_at DESC
    """
)
```

## UI/UX Best Practices

1. **Non-blocking dialog**: `dialog.exec()` запускается async, UI остаётся responsive
2. **Toast notifications**: все статусы через toast (не modal dialogs)
3. **Progress feedback**: "Downloading...", "Rendering...", "Uploading..." toasts
4. **Error recovery**: при ошибке input re-enabled, можно попробовать снова
5. **Visual feedback**: ROI rectangle с полупрозрачной заливкой
6. **Model suggestions**: показать в sidebar что модель запрашивает

## Summary

ROI workflow реализован полностью:
- ✅ PDFRenderer с clip optimization
- ✅ ImageViewerDialog с pan/zoom/ROI selection
- ✅ Full pipeline: download → render → upload → model
- ✅ Artifacts persistence
- ✅ Error handling
- ✅ Toast notifications
- ✅ Async operations
- ✅ Tests

MVP ready! 🎉
