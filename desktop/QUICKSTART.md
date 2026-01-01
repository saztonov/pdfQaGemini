# pdfQaGemini Desktop - Quick Start Guide

## Полный MVP Desktop приложения готов! 🎉

### Что реализовано

- ✅ Desktop приложение на PySide6 + qasync
- ✅ 3 панели: Projects Tree | Chat | Context & Gemini Files
- ✅ Lazy loading дерева проектов
- ✅ Загрузка файлов в Gemini Files API
- ✅ Чат с моделью (structured output)
- ✅ Image Viewer с ROI selection
- ✅ PDF rendering (preview + high-quality ROI)
- ✅ Полный ROI workflow: выделение → render → upload → model
- ✅ Async операции (UI никогда не блокируется)
- ✅ Toast notifications
- ✅ LRU file cache
- ✅ Message persistence (Supabase)
- ✅ Artifacts storage (R2 + metadata)
- ✅ 45+ files, 4500+ LOC
- ✅ 10 test files с моками

## Установка

### 1. Зависимости

```bash
cd desktop
pip install -e ".[dev]"
```

**Основные пакеты:**
- PySide6 (Qt UI)
- qasync (async Qt loop)
- pydantic (validation)
- httpx (async HTTP)
- google-genai (Gemini API)
- pymupdf (PDF render)
- pillow (images)
- cachetools (LRU cache)
- boto3 (R2 upload)
- supabase (database)
- python-dotenv (config)

### 2. База данных

**Supabase SQL Editor:**

```sql
-- Скопировать содержимое:
-- desktop/app/db/migrations/001_pdfQaGemini_qa.sql
-- И выполнить в SQL Editor
```

Создаст 6 таблиц:
- `qa_conversations`
- `qa_messages`
- `qa_conversation_nodes`
- `qa_artifacts`
- `qa_gemini_files`
- `qa_conversation_gemini_files`

И RPC функцию: `qa_get_descendants()`

### 3. Конфигурация

**При первом запуске:**
- Toast: "⚙️ Приложение не настроено. Откройте Settings."

**Откройте Settings (toolbar):**

**General tab:**
- Client ID: `your_client_id`
- Default Model: `gemini-3-flash-preview`
- Cache Directory: `./cache`
- Cache Size (MB): `500`

**Supabase tab:**
- URL: `https://your-project.supabase.co`
- Key: `your_supabase_key`

**Cloudflare R2 tab:**
- Public Base URL: `https://pub-xxx.r2.dev`
- Endpoint: `https://xxx.r2.cloudflarestorage.com`
- Bucket: `your-bucket`
- Access Key: `your_r2_access_key`
- Secret Key: `your_r2_secret_key`

**Gemini tab:**
- API Key: `your_gemini_api_key`

**Click Save** → Toast: "Настройки сохранены"

## Запуск

```bash
cd desktop
python -m app.main
```

Или:

```bash
python app/main.py
```

## Workflow

### 1. Connect

Click **Connect** в toolbar → загружает `.env` → инициализирует сервисы → создаёт conversation.

**Toast notifications:**
- "Connect: загрузка настроек..."
- "Подключено успешно" ✓

### 2. Load Projects Tree

**LeftProjectsPanel:**
1. В поле `Client ID` введи `CLIENT_ID` из `.env` (или автоматически подставится)
2. Click **Refresh** → загружает root nodes
3. Раскрывай узлы (lazy loading детей)
4. Выбери проекты/документы (Ctrl+Click для множественного выбора)
5. Click **Add Selected to Context**

**Что происходит:**
- RPC `qa_get_descendants()` → находит все document nodes рекурсивно
- Emit `addToContextRequested(document_node_ids)`
- MainWindow добавляет в `context_node_ids`
- Toast: "Добавлено N узлов в контекст. Нажмите 'Load Node Files'..."

### 3. Load Context Files

**RightContextPanel → Context tab:**
1. Click **Load Node Files**
   - Fetches `node_files` для всех context nodes одним запросом
   - Создаёт `ContextItem[]`
   - Отображает в таблице: Title, File Type, File Name, MIME, R2 Key, Status

**Toast:**
- "Загрузка файлов для N узлов..."
- "Загружено N файлов" ✓

### 4. Upload to Gemini Files

**RightContextPanel → Context tab:**
1. Выбери файлы в таблице (Ctrl+Click)
2. Click **Upload Selected to Gemini**

**Что происходит (async):**
- Download от R2 → cache (streaming)
- Upload в Gemini Files API
- Update `ContextItem.status = "uploaded"`
- Update `ContextItem.gemini_name`
- Add to `attached_gemini_files[]`

**Toast:**
- "Загрузка N файлов в Gemini..."
- "Загружено N файлов в Gemini" ✓

### 5. Verify Gemini Files

**RightContextPanel → Gemini Files tab:**
1. Click **Refresh**
   - Calls `gemini_client.list_files()`
   - Отображает: Display Name, Name, MIME, Size, Created, Expires

**Toast:**
- "Обновление Gemini Files..."
- "Загружено N файлов из Gemini" ✓

### 6. Ask Question

**ChatPanel:**
1. В input field введи вопрос: "Что содержится в этом документе?"
2. Press Enter или Click **Отправить**

**Что происходит (async):**
- Disable input (prevent spam)
- Добавляет user message в чат
- Toast: "Отправка запроса модели..."
- `Agent.ask()`:
  - Save user message → `qa_messages`
  - `GeminiClient.generate_structured()` с file_uris
  - Returns `ModelReply` (JSON по схеме)
  - Save assistant message → `qa_messages`
- Добавляет assistant message в чат с metadata:
  - Model: gemini-3-flash-preview
  - Thinking: low
  - Actions: [...]
  - Is final: false/true
- Process actions (если есть)
- Enable input
- Toast: "Ответ получен" ✓

### 7. ROI Extraction (если модель запрашивает)

**Модель может вернуть action:**
```json
{
  "type": "request_roi",
  "payload": {
    "image_ref": "context_item_id",
    "hint_text": "Выделите таблицу в верхней части"
  },
  "note": "Нужна таблица с данными"
}
```

**Что происходит автоматически:**
1. Download PDF from R2 → cache
2. Render preview (150 DPI) → QImage
3. Open **ImageViewerDialog**:
   - Pan/zoom с mouse drag
   - Zoom с mouse wheel
   - Model suggestions в sidebar
4. User:
   - Click **Enable ROI Selection**
   - Draw rectangle на изображении
   - (Optional) Add note: "Таблица с финансовыми данными"
   - Click **Confirm ROI**
5. **ROI Processing** (async):
   - Render ROI high-quality (400 DPI, clip only ROI region)
   - Upload PNG → R2 (`artifacts/{conversation_id}/roi_*.png`)
   - Save metadata → `qa_artifacts` (bbox_norm, user_note, source)
   - Upload PNG → Gemini Files API
   - **Ask model again** с ROI file_uri:
     - `user_text = "Пользователь выделил область. Примечание: ..."`
     - `file_uris = [original_files..., roi_file_uri]`
   - Display assistant reply в чате
6. Toast notifications на каждом шаге ✓

**ImageViewerDialog controls:**
- **Enable ROI Selection**: toggle режим выделения
- **Clear ROI**: очистить текущее выделение
- **Fit to View**: вписать изображение в viewport
- **Confirm ROI**: подтвердить и обработать
- **Reject / Close**: отменить

## Testing

```bash
cd desktop
pytest
```

**Запустить конкретный тест:**
```bash
pytest tests/test_agent.py -v
pytest tests/test_pdf_render.py::TestPDFRenderer::test_render_roi -v
```

**Coverage:**
- Все services с моками (Supabase, Gemini, R2)
- UI components (panels, dialogs)
- PDF rendering
- ROI workflow
- Validation schemas

## Architecture Highlights

### Async Everywhere
- `qasync` event loop для PySide6
- `@asyncSlot` для UI handlers
- `asyncio.to_thread()` для sync clients (Supabase, Gemini, boto3)
- `httpx.AsyncClient` для streaming downloads

### Lazy Loading
- Tree nodes: children загружаются при раскрытии
- Files: fetch по запросу (`Load Node Files`)
- Chunked queries: `fetch_node_files()` разбивает на 200 ID chunks

### Cache
- LRU cache для downloaded files (500 MB default)
- Eviction по size + LRU order
- Cache key = URL hash или item_id

### Toast Notifications
- 4 типа: info, success, warning, error
- Очередь с позиционированием (стек)
- Правый верхний угол
- Auto-hide (2-4 сек)
- Неблокирующие

### Structured Output
- `ModelReply` schema → JSON schema для Gemini
- Validation через Pydantic
- Actions: answer, open_image, request_roi, final

### Performance
- PyMuPDF `clip` для ROI (НЕ рендерим всю страницу)
- DPI levels: 150 preview, 400 ROI
- Semaphore для download concurrency
- Streaming download (8KB chunks)

## Troubleshooting

### "Supabase repo not initialized"
- Click **Connect** first
- Check `.env` credentials

### "Cannot find file reference"
- Click **Load Node Files** в Context tab
- Verify files in table

### "Gemini API Error"
- Check `GEMINI_API_KEY` в `.env`
- Verify API key permissions

### "R2 Upload Failed"
- Check R2 credentials в `.env`
- Verify bucket exists and accessible

### Image Viewer не открывается
- Check PDF file в cache (downloaded?)
- Check toast для error details

### ROI не рендерится
- Verify PyMuPDF installed: `pip list | grep PyMuPDF`
- Check PDF format (должен быть валидный PDF)

## Key Files

### Entry Point
- `app/main.py`: qasync loop + MainWindow

### UI
- `app/ui/main_window.py`: координация + state + toolbar
- `app/ui/left_projects_panel.py`: tree + lazy loading
- `app/ui/chat_panel.py`: HTML messages + input
- `app/ui/right_context_panel.py`: Context + Gemini Files tabs
- `app/ui/image_viewer.py`: ROIGraphicsView + ImageViewerDialog
- `app/ui/toast.py`: ToastManager + ToastWidget

### Services
- `app/services/supabase_repo.py`: 11 async methods
- `app/services/gemini_client.py`: Files API + generation
- `app/services/r2_async.py`: download/upload + cache
- `app/services/agent.py`: ask() + MODEL_REPLY_SCHEMA
- `app/services/cache.py`: CacheManager (LRU)
- `app/services/pdf_render.py`: PDFRenderer (preview + ROI)

### Models
- `app/models/schemas.py`: 9 Pydantic models

### Database
- `app/db/migrations/001_pdfQaGemini_qa.sql`: 6 tables + RPC

## Documentation

- `README.md`: Overview + setup
- `ARCHITECTURE.md`: Detailed architecture
- `MVP_STATUS.md`: What's done, what's not
- `ROI_WORKFLOW.md`: ROI extraction deep dive
- `QUICKSTART.md`: This file!

## Next Steps

1. **Test with real data**:
   - Load your Supabase tree_nodes
   - Upload PDFs to R2
   - Test full workflow

2. **Customize system prompt**:
   - Edit `SYSTEM_PROMPT` в `app/services/agent.py`

3. **Adjust model settings**:
   - Change `DEFAULT_MODEL` в `.env`
   - Modify `thinking_level` в `Agent.ask()`

4. **Extend actions**:
   - Add new action types в `ModelAction`
   - Implement handlers в `MainWindow._process_model_actions()`

5. **Add Model Inspector**:
   - Implement `app/ui/model_inspector.py`
   - Show thinking traces, timing, etc.

## Model Inspector

**Toolbar → "Model Inspector"**

Отдельное окно для мониторинга вызовов модели:
- Список traces (время, модель, latency, is_final)
- Детали: system_prompt, user_text, input_files, response JSON, actions, errors
- Copy Request/Response JSON
- Auto-refresh каждые 2 секунды

**Use cases:**
- Debug structured output
- Optimize performance (check latency)
- Analyze model behavior
- Share debug info (copy JSON)

**Storage:** In-memory, последние 200 traces (LRU eviction).

См. `INSPECTOR_GUIDE.md` для деталей.

## Support

Если что-то не работает:

1. Check console output (stderr)
2. Check toast notifications
3. Check `.env` credentials
4. Run tests: `pytest -v`
5. Read error messages в chat panel (system messages)

## MVP Complete! 🎉

Desktop приложение **pdfQaGemini** полностью готово для использования.

**Основной workflow:**
1. Connect
2. Load tree
3. Add to context
4. Load files
5. Upload to Gemini
6. Ask questions
7. (Optional) Select ROI
8. Get answers

Enjoy! 🚀
