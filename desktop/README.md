# pdfQaGemini Desktop MVP

Desktop приложение для работы с PDF через Gemini API.

## Требования

- Python 3.10+
- Windows/Linux/macOS

## Установка

```bash
cd desktop
pip install -e .
```

Для разработки:

```bash
pip install -e ".[dev]"
```

## Тесты

```bash
cd desktop
pytest
```

## Настройка

### Вариант 1: Через UI (рекомендуется)

1. Запустите приложение
2. Откройте **Settings** в toolbar
3. Заполните вкладки:
   - **General**: Client ID, Default Model, Cache settings
   - **Supabase**: URL, Key
   - **Cloudflare R2**: Public URL, Endpoint, Bucket, Access/Secret keys
   - **Gemini**: API Key
4. Click **Save**
5. Click **Connect** в toolbar

Настройки сохраняются в QSettings (платформо-зависимое хранилище).

### Вариант 2: Через .env (legacy)

```bash
cd desktop
cp env.example .env
# Отредактировать .env с вашими настройками
```

**Note:** QSettings имеет приоритет над .env файлом.

## Запуск

```bash
cd desktop
python -m app.main
```

Или:

```bash
cd desktop
python app/main.py
```

## Структура

```
desktop/
  app/
    main.py              # Точка входа
    ui/                  # UI компоненты
      main_window.py     # Главное окно
      toast.py           # Всплывающие уведомления
    services/            # Сервисы (Supabase, R2, Gemini, etc)
    models/              # Pydantic схемы
    utils/               # Утилиты
```

## База данных (Supabase)

### Миграция

Открыть Supabase SQL Editor и выполнить:

```sql
-- Скопировать содержимое app/db/migrations/001_pdfQaGemini_qa.sql
```

Или через CLI:

```bash
supabase db push --file app/db/migrations/001_pdfQaGemini_qa.sql
```

### Таблицы MVP

- `qa_conversations` - чаты
- `qa_messages` - сообщения (user/assistant/tool/system)
- `qa_conversation_nodes` - контекст (tree_nodes)
- `qa_artifacts` - артефакты (ROI, экспорт)
- `qa_gemini_files` - кеш Gemini Files API
- `qa_conversation_gemini_files` - связь чатов с файлами

### RPC функции

- `qa_get_descendants(client_id, root_ids[], node_types[])` - рекурсивный запрос потомков

## MVP функционал

- ✓ Три панели: Projects | Chat | Context
- ✓ Toast уведомления (неблокирующие)
- ✓ Tree view проектов (ленивая загрузка)
- ✓ Чат интерфейс с историей
- ✓ Context panel с загрузкой в Gemini Files
- ✓ Agent с structured output (ModelReply)
- ✓ Async операции без блокировки UI
- ✓ Image Viewer с pan/zoom и ROI selection
- ✓ ROI extraction workflow (render → upload → ask model)
- ✓ PDF rendering с PyMuPDF (preview + high-quality ROI)
- ✓ Model Inspector (trace list + details, copy JSON, auto-refresh)

## Архитектура

```
UI Layer:
- MainWindow (toolbar, state, coordination)
- LeftProjectsPanel (tree_nodes, lazy loading)
- ChatPanel (message history, input)
- RightContextPanel (Context + Gemini Files tabs)

Service Layer:
- SupabaseRepo (async data access)
- GeminiClient (Files API + structured generation)
- R2AsyncClient (download/upload, cache)
- Agent (orchestrates Q&A flow)
- CacheManager (LRU file cache)

Models:
- Pydantic schemas (TreeNode, NodeFile, Conversation, Message, ContextItem, ModelReply)
```

## Workflow MVP

1. Click **Connect** → загружает .env, инициализирует сервисы, создаёт conversation
2. В LeftProjectsPanel: введите Client ID → **Refresh** → выберите проекты/документы → **Add Selected to Context**
3. В RightContextPanel → tab Context → **Load Node Files** → выберите файлы → **Upload Selected to Gemini**
4. В RightContextPanel → tab Gemini Files → **Refresh** для проверки загруженных файлов
5. В ChatPanel: задайте вопрос → Agent отправит запрос с file_uris → получит structured ModelReply
6. Ответ отобразится в чате с метаданными (model, thinking, actions, is_final)
