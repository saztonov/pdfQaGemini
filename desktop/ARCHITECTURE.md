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
- При раскрытии узла: fetch_children()
- При Add to Context: get_descendant_documents() → emit addToContextRequested

#### ChatPanel
- QTextEdit для истории (read-only, HTML formatting)
- QLineEdit + QPushButton для ввода
- Методы: add_user_message, add_assistant_message, add_system_message
- Emit: askModelRequested(user_text)

#### RightContextPanel
- QTabWidget: Context + Gemini Files
- Context tab: таблица ContextItem, кнопки Load/Upload/Detach
- Gemini Files tab: таблица list_files(), кнопки Refresh/Delete
- Emit: uploadContextItemsRequested, refreshGeminiRequested

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

### Add Documents to Context
```
User selects nodes in tree
  → LeftProjectsPanel.add_selected_to_context()
    → SupabaseRepo.get_descendant_documents(root_ids, node_types=["document"])
      → emit addToContextRequested(document_node_ids)
        → MainWindow._on_nodes_add_context()
          → RightContextPanel.set_context_node_ids()

User clicks "Load Node Files"
  → RightContextPanel.load_node_files()
    → SupabaseRepo.fetch_node_files(context_node_ids)
      → creates ContextItem[] → updates context_table
```

### Upload to Gemini
```
User selects files, clicks "Upload Selected to Gemini"
  → RightContextPanel.upload_selected_to_gemini()
    → emit uploadContextItemsRequested(item_ids)
      → MainWindow._on_upload_context_items()
        → for each item:
            R2AsyncClient.download_to_cache(r2_key)
            GeminiClient.upload_file(cached_path)
            update ContextItem status + gemini_name
            add to attached_gemini_files[]
```

### Ask Model
```
User types question, presses Send
  → ChatPanel emit askModelRequested(user_text)
    → MainWindow._on_ask_model()
      → collect file_uris from attached_gemini_files
      → Agent.ask(conversation_id, user_text, file_uris)
        → save user message to qa_messages
        → GeminiClient.generate_structured(system_prompt, user_text, file_uris, schema)
          → returns ModelReply
        → save assistant message to qa_messages
      → ChatPanel.add_assistant_message(reply.assistant_text, meta)
      → _process_model_actions(reply.actions)
```

## Database Schema (Supabase)

### Existing Tables
- `tree_nodes`: проектная структура
- `node_files`: файлы документов

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

## Testing

```bash
pytest
pytest tests/test_agent.py -v
pytest tests/test_supabase_repo.py -v
```

Используются моки для всех внешних зависимостей (Supabase, Gemini, R2).

## Future Enhancements

- Model Inspector (trace + thinking display)
- Image Viewer (увеличение изображений)
- ROI extraction UI
- Pro model fallback для is_final=true
- WebSocket для real-time updates
- Batch operations
- Export/Import conversations
