# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

### Desktop Client
```bash
cd desktop
pip install -e .              # Basic install
pip install -e ".[dev]"       # With dev tools (black, ruff)
python -m app.main            # Run desktop app
```

### Server
```bash
cd server
pip install -e .
python -m app.main            # Or: uvicorn app.main:app --reload
```

### Code Quality
```bash
pre-commit run --all-files
black . --line-length=100
ruff check . --fix
```

## Database Migrations

1. Run in Supabase SQL Editor: `desktop/app/db/migrations/prod.sql`
2. Enable Realtime: `server/migrations/001_enable_realtime.sql`

## Architecture Overview

**Client-Server architecture** for PDF Q&A using Google Gemini API.

### Project Structure

```
pdfQaGemini/
├── desktop/            # Desktop client (PySide6 UI)
│   └── app/
│       ├── ui/         # Qt UI components
│       └── services/   # api_client.py, realtime_client.py, pdf_render.py
│
├── server/             # FastAPI server
│   └── app/
│       ├── api/routes/ # REST API endpoints
│       ├── services/   # agent.py, gemini_client.py, supabase_repo.py
│       └── models/     # Pydantic schemas
```

### Operation Modes

**Local Mode** (Server URL empty):
- Desktop client calls Gemini API directly
- Agent runs locally with full agentic loop (request_files, request_roi, final)
- Suitable for development/testing

**Server Mode** (Server URL configured):
- Desktop sends requests via `APIClient` to server
- Server creates background job, processes via `JobProcessor`
- Client receives updates via `RealtimeClient` (Supabase Realtime)
- If client disconnects before response, result saved to DB and visible on reconnect

### Server Architecture

```
Client → POST /messages → Save user msg + Create job → Return immediately
                                    ↓
                        JobProcessor (background loop)
                                    ↓
                        Agent.ask_question() → Gemini API
                                    ↓
                        Save assistant msg + Update job → completed
                                    ↓
                        Supabase Realtime → Client notification
```

### Key Design

- **Async jobs**: LLM requests processed in background via `qa_jobs` table
- **Supabase Realtime**: Client subscribes to job/message updates
- **Offline support**: If client disconnects, results saved to DB; visible on reconnect

### Key Patterns

- **qasync.QEventLoop** integrates asyncio with Qt
- **@asyncSlot** decorators for UI event handlers
- **asyncio.to_thread()** wraps sync SDK calls (Supabase, Gemini, boto3)
- **Lazy loading** everywhere (tree nodes, files, Gemini Files)
- **Toast notifications** for all user feedback (no blocking dialogs)
- **Structured output** - Gemini responses validated against JSON schema (ModelReply)

### Configuration

Priority: QSettings (OS-level) > .env file. Configure via Settings dialog in app.

### Database Tables (Supabase)

Custom tables: `qa_conversations`, `qa_messages`, `qa_jobs`, `qa_conversation_nodes`, `qa_artifacts`, `qa_gemini_files`, `qa_conversation_gemini_files`

Existing tables: `tree_nodes`, `node_files`

### API Endpoints (Server)

- `POST /api/v1/conversations` - Create conversation
- `GET /api/v1/conversations/{id}/messages` - List messages
- `POST /api/v1/conversations/{id}/messages` - Send message (creates job)
- `GET /api/v1/jobs/{id}` - Job status
- `POST /api/v1/files/upload` - Upload to Gemini

## Code Style

- Line length: 100
- Python 3.10+
- Type hints required
- Async for all I/O operations
- Pydantic for data validation

## Guidelines (from .cursorrules)

- Minimal responses, code-only blocks
- MVP only - no speculative features
- No tests/docs unless explicitly requested
- Minimal code comments
- Verify against official library docs when uncertain
