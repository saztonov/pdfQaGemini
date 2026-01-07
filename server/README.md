# pdfQaGemini Server

FastAPI сервер для обработки LLM запросов.

## Установка

```bash
cd server
pip install -e .
```

## Настройка

Скопируйте `env.example` в `.env` и заполните переменные:

```bash
cp env.example .env
```

## Запуск

```bash
cd server
python -m app.main
```

Или через uvicorn:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API

Swagger UI: http://localhost:8000/docs

### Endpoints

- `GET /api/v1/health` - Health check
- `POST /api/v1/conversations` - Создать чат
- `GET /api/v1/conversations` - Список чатов
- `POST /api/v1/conversations/{id}/messages` - Отправить сообщение (создаёт job)
- `GET /api/v1/conversations/{id}/messages` - Список сообщений
- `GET /api/v1/jobs/{id}` - Статус задачи
- `POST /api/v1/files/upload` - Загрузить файл в Gemini

## Архитектура

```
Client → POST /messages → Сохранение user message + Создание job → Return
                                      ↓
                              JobProcessor (фон)
                                      ↓
                              Agent.ask_question()
                                      ↓
                              Сохранение assistant message
                                      ↓
                              Обновление job status → completed
                                      ↓
                         Supabase Realtime → Client получает уведомление
```

## База данных

Выполните миграцию в Supabase SQL Editor:

1. `desktop/app/db/migrations/prod.sql` - основные таблицы
2. `server/migrations/001_enable_realtime.sql` - включение Realtime

## Структура

```
server/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Settings
│   ├── api/
│   │   ├── dependencies.py  # DI
│   │   └── routes/          # API endpoints
│   ├── services/
│   │   ├── agent.py         # LLM orchestration
│   │   ├── gemini_client.py # Gemini API
│   │   ├── supabase_repo.py # Database
│   │   ├── r2_async.py      # R2 storage
│   │   └── job_processor.py # Background worker
│   └── models/
│       └── schemas.py       # Pydantic models
└── migrations/
    └── 001_enable_realtime.sql
```
