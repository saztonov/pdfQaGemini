# MVP Status - pdfQaGemini Desktop

## ✅ Completed

### 1. Project Structure
```
desktop/
  app/
    main.py              ✓ qasync integration + startup check
    ui/
      main_window.py     ✓ toolbar, state, panels, Settings integration
      left_projects_panel.py  ✓ tree with lazy loading
      chat_panel.py      ✓ HTML chat history, input
      right_context_panel.py  ✓ Context + Gemini Files tabs
      toast.py           ✓ 4 types, queue, positioning
      model_inspector.py ✓ ModelInspectorWindow (trace list + details)
      image_viewer.py    ✓ ROIGraphicsView + ImageViewerDialog
      settings_dialog.py ✓ Settings with QSettings persistence
    services/
      supabase_repo.py   ✓ 11 async methods
      r2_async.py        ✓ httpx + boto3, cache
      gemini_client.py   ✓ Files API + structured gen
      agent.py           ✓ ask() with ModelReply schema
      cache.py           ✓ LRU cache manager
      pdf_render.py      ✓ PyMuPDF render (preview + ROI with clip)
      trace.py           ✓ ModelTrace + TraceStore (in-memory)
    models/
      schemas.py         ✓ 9 pydantic models
    utils/
      errors.py          ✓ custom exceptions
    db/
      migrations/
        001_pdfQaGemini_qa.sql  ✓ 6 tables + RPC
  pyproject.toml         ✓ dependencies
  env.example            ✓ config template
  README.md              ✓ setup + workflow
  ARCHITECTURE.md        ✓ detailed docs
```

### 2. Database (Supabase)
- ✓ 6 tables: qa_conversations, qa_messages, qa_conversation_nodes, qa_artifacts, qa_gemini_files, qa_conversation_gemini_files
- ✓ Indexes для performance
- ✓ RPC function: qa_get_descendants()
- ✓ No RLS (as per requirements)

### 3. UI Components
- ✓ MainWindow: toolbar, 3-panel splitter, state management
- ✓ LeftProjectsPanel: QTreeWidget, lazy loading, прямая загрузка в Gemini
- ✓ ChatPanel: HTML chat, streaming thoughts, **выбор файлов через чипы**, model/thinking selector
- ✓ RightContextPanel: **единая панель Gemini Files** с чекбоксами для выбора файлов
- ✓ ToastManager: 4 types (info/success/warning/error), non-blocking, stacked

### 4. Services
- ✓ SupabaseRepo: 11 methods (fetch_roots, fetch_children, get_descendant_documents, fetch_node_files, qa_*)
- ✓ GeminiClient: Files API (list/upload/delete), generate_structured, generate_simple
- ✓ R2AsyncClient: download_to_cache (streaming), upload_bytes, upload_file, build_public_url
- ✓ Agent: ask() method, MODEL_REPLY_SCHEMA, SYSTEM_PROMPT, message persistence
- ✓ CacheManager: LRU eviction, size limit, get_path, put

### 5. Data Models
- ✓ TreeNode, NodeFile (DB)
- ✓ Conversation, Message (QA)
- ✓ ContextItem (UI)
- ✓ ModelAction, ModelReply (Agent)
- ✓ Validation with field_validator

### 6. Async Architecture
- ✓ qasync event loop integration
- ✓ asyncSlot decorators for UI handlers
- ✓ asyncio.to_thread for sync clients (Supabase, Gemini, boto3)
- ✓ httpx.AsyncClient for streaming downloads
- ✓ Semaphore for concurrency control

## 🔄 Workflow Implementation

### Упрощённый User Flow (v2)
1. ✓ Startup → auto-connect если настроено → toast если нет
2. ✓ Settings → configure Supabase/R2/Gemini → save to QSettings
3. ✓ Connect → инициализация сервисов → загрузка Gemini Files
4. ✓ **LeftPanel: выбор файлов → "📤 Загрузить в Gemini" → мгновенная загрузка**
5. ✓ **RightPanel: автообновление списка Gemini Files с чекбоксами**
6. ✓ **ChatPanel: выбор файлов через чипы → ввод вопроса → отправка**
7. ✓ Streaming thoughts + answer display
8. ✓ Process actions (open_image, request_roi, final)

## ⏳ Not Implemented (Out of MVP Scope)
- Pro model fallback for is_final=true
- Artifacts management UI (backend готов, UI нет)
- Export/Import conversations
- Settings/preferences UI
- Multi-page PDF support (пока только page 0)
- Batch ROI processing

## 📋 Known Limitations (MVP)

1. No RLS - security через application logic
2. ~~Gemini Files всегда с mime_type="application/pdf"~~ ✓ ИСПРАВЛЕНО - определяется автоматически
3. ~~Context item status только локально~~ ✓ УДАЛЕНО - Context tab убран, прямая загрузка в Gemini
4. Один активный conversation per session (можно добавить список)
5. ~~Thinking level hardcoded "low"~~ ✓ ИСПРАВЛЕНО - селектор в ChatPanel
6. No pagination для больших списков (MVP достаточно)

## 🚀 Ready to Run

```bash
# 1. Setup
cd desktop
pip install -e ".[dev]"
cp env.example .env
# Edit .env with your credentials

# 2. Database
# Apply migration in Supabase SQL Editor:
# Copy content of app/db/migrations/001_pdfQaGemini_qa.sql

# 3. Run
python -m app.main
```

## 📊 Statistics

- Python LOC: ~5200
- Dependencies: 10 main packages
- Tables: 6 QA + 2 existing
- UI panels: 4 main + ImageViewerDialog + ModelInspectorWindow
- Service classes: 7 (Supabase, Gemini, R2, Agent, Cache, PDFRenderer, TraceStore)
- Pydantic models: 10 (including ModelTrace)

## 🎯 MVP Goals Achieved

- ✅ Fast UI (async, no blocking)
- ✅ Lazy loading (tree, files)
- ✅ Toast notifications only
- ✅ Structured Gemini output
- ✅ Context management
- ✅ Message persistence
- ✅ ROI workflow (selection → render → upload → model)
- ✅ PDF rendering with clip optimization
- ✅ Model Inspector (trace list + details + copy JSON)
- ✅ Tracing (ModelTrace + TraceStore in-memory)
- ✅ Settings dialog (QSettings persistence)
- ✅ Startup configuration check
- ✅ Clean architecture
- ✅ Testable code
- ✅ Type hints everywhere
- ✅ Russian UI strings

## Next Steps (Post-MVP)

1. Persist traces to database (optional)
2. Multi-page PDF support (page selector)
3. Batch ROI operations
4. Conversation management (list, switch, delete)
5. Pro model для финальных ответов
6. Export results (PDF with annotations)
7. Settings persistence
8. Artifacts browser UI
9. ROI history/annotations overlay
