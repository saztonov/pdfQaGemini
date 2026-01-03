# pdfQaGemini Desktop Architecture

## Overview

Desktop приложение на PySide6 + qasync для работы с PDF документами через Gemini API с использованием Supabase для хранения данных и Cloudflare R2 для файлов.

## Core Principles

1. **Non-blocking UI**: все длительные операции выполняются async через qasync
2. **Lazy loading**: данные загружаются по требованию (дерево, файлы)
3. **Toast notifications**: все уведомления через ToastManager (неблокирующие)
4. **Structured output**: Gemini возвращает JSON по схеме ModelReply
5. **Caching**: файлы кешируются локально с LRU eviction

## Layers

### UI Layer (`app/ui/`)

#### MainWindow
- Координирует все панели
- Управляет состоянием (client_id, conversation_id, context_node_ids, attached_gemini_files)
- Обрабатывает сигналы от панелей
- Toolbar с основными действиями

#### LeftProjectsPanel
- QTreeWidget с ленивой загрузкой детей
- При раскрытии узла: fetch_children() для не-документов, fetch_node_files_single() для документов
- При Add to Context: get_descendant_documents() → emit addToContextRequested

##### Отображение файлов документа в дереве
- Под документом раскрывающийся контейнер "📎 Файлы (N)"
- Основные файлы: annotation (📋), ocr_html (📝), result_json (📊)
- Группа "✂️ Кропы (N)" с вложенными файлами (🖼️)
- PDF не дублируется (только как сам документ)

#### ChatPanel
- QTextBrowser для истории (read-only, HTML formatting, collapsible thoughts)
- Улучшенная форма ввода с:
  - Выбором файлов через чипы (FileChip)
  - Кнопками "Все" / "Снять" для быстрого выбора
  - Селектором модели и уровня thinking
- Методы: add_user_message, add_assistant_message, set_available_files
- Emit: askModelRequested(user_text, model_name, thinking_level, file_refs)

#### RightContextPanel
- Единая панель Gemini Files (без вкладок)
- Таблица загруженных файлов с чекбоксами для выбора
- Кнопки: Обновить, Удалить, Выбрать все, Снять выбор
- Автоматическое обновление после загрузки файлов
- Emit: refreshGeminiRequested, filesSelectionChanged

#### ToastManager
- Очередь всплывающих уведомлений
- 4 типа: info, success, warning, error
- Позиционирование: правый верхний угол, стеком

### Service Layer (`app/services/`)

#### SupabaseRepo
- Async wrapper для Supabase client (через asyncio.to_thread)
- Методы для tree_nodes, node_files, qa_* таблиц
- RPC: qa_get_descendants

#### GeminiClient
- Async wrapper для google-genai SDK
- Files API: list_files, upload_file, delete_file
- Generation: generate_structured (JSON schema), generate_simple
- Использует asyncio.to_thread для синхронного SDK

#### R2AsyncClient
- httpx.AsyncClient для download (streaming)
- boto3 через asyncio.to_thread для upload
- Семафор для ограничения параллелизма
- Методы: build_public_url, download_to_cache, upload_bytes, upload_file

#### Agent
- Orchestrator для Q&A
- Метод ask(): user_text + file_uris → generate_structured → ModelReply
- Сохраняет user/assistant messages в qa_messages
- SYSTEM_PROMPT: короткий промпт на русском
- MODEL_REPLY_SCHEMA: JSON schema для structured output

#### CacheManager
- LRU кеш файлов с size limit
- OrderedDict для tracking
- Методы: get_path, put, put_file, evict_oldest, clear

### Models Layer (`app/models/`)

#### Pydantic Schemas
- TreeNode, NodeFile (DB entities)
- Conversation, Message (QA entities)
- ContextItem (UI entity для правой панели)
- ModelAction, ModelReply (Agent outputs)

## Data Flow

### Упрощённый Workflow (Select → Upload → Ask)

```
1. Выбор файлов в дереве → Мгновенная загрузка в Gemini
   User selects nodes/files in tree → clicks "📤 Загрузить в Gemini"
     → LeftProjectsPanel.add_selected_to_context()
       → emit addToContextRequested(node_ids) или addFilesToContextRequested(files_info)
         → MainWindow._upload_files_to_gemini(files_info)
           → for each file:
               R2AsyncClient.download_to_cache(r2_key)
               GeminiClient.upload_file(cached_path)
           → RightContextPanel.refresh_files()  # автообновление
           → ChatPanel.set_available_files()    # синхронизация с чатом

2. Выбор файлов для запроса (в ChatPanel)
   User clicks file chips in input form
     → _selected_files updated
     → visual feedback (blue selected, gray unselected)

3. Отправка запроса с выбранными файлами
   User types question, selects files, presses Send
     → ChatPanel emit askModelRequested(text, model, thinking, file_refs)
       → MainWindow._on_ask_model()
         → Agent.ask_stream(conversation_id, user_text, file_refs, model, thinking_level)
           → streaming thoughts → ChatPanel.append_thought_chunk()
           → streaming answer → ChatPanel.append_answer_chunk()
         → ChatPanel.add_assistant_message(answer, meta)
```

## Database Schema (Supabase)

### Existing Tables
- `tree_nodes`: проектная структура
- `node_files`: все файлы привязанные к узлам (PDF, аннотации, OCR, результаты, кропы)

### Структура хранения файлов
- **Supabase (node_files)**: метаданные всех файлов
- **R2**: сами файлы

### Типы файлов (FileType enum)
- `pdf` — исходный PDF документ
- `annotation` — разметка блоков ({name}_annotation.json)
- `ocr_html` — HTML результат OCR ({name}_ocr.html)
- `result_json` — полный результат обработки ({name}_result.json)
- `crop` — кропы изображений (в папке crops/)

### QA Tables (created by migration 001)
- `qa_conversations`: чаты
- `qa_messages`: сообщения (user/assistant/tool/system)
- `qa_conversation_nodes`: связь чата с узлами (контекст)
- `qa_artifacts`: артефакты (ROI images, exports)
- `qa_gemini_files`: кеш Gemini Files API
- `qa_conversation_gemini_files`: связь чата с Gemini files

### RPC Functions
- `qa_get_descendants(client_id, root_ids[], node_types[])`: рекурсивный поиск потомков

## Configuration (.env)

```bash
# CLIENT_ID: уникальный идентификатор для multi-tenancy (email, компания, username)
CLIENT_ID=your_email@example.com
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=xxx
GEMINI_API_KEY=xxx
R2_ACCOUNT_ID=xxx
R2_ACCESS_KEY_ID=xxx
R2_SECRET_ACCESS_KEY=xxx
R2_BUCKET_NAME=xxx
R2_PUBLIC_URL=https://pub-xxx.r2.dev
CACHE_DIR=./cache
DEFAULT_MODEL=gemini-3-flash-preview
```

## Performance Optimizations

1. **Lazy loading**: tree nodes, children по требованию
2. **Chunked requests**: fetch_node_files разбивает на чанки по 200
3. **Semaphore**: R2AsyncClient ограничивает параллельные download
4. **LRU cache**: локальный кеш файлов с eviction
5. **Async everywhere**: qasync event loop, asyncio.to_thread для sync clients
6. **Thinking level**: default "low" для быстрых ответов

## Future Enhancements

- Model Inspector (trace + thinking display)
- Image Viewer (увеличение изображений)
- ROI extraction UI
- Pro model fallback для is_final=true
- WebSocket для real-time updates
- Batch operations
- Export/Import conversations
