# Model Inspector Guide

## Overview

Model Inspector - окно для мониторинга и отладки вызовов к Gemini API. Показывает все детали каждого запроса: промпты, файлы, ответы, тайминги, ошибки.

## Opening Inspector

**MainWindow toolbar → "Model Inspector"**

Откроется отдельное окно (singleton). Можно держать открытым параллельно с основной работой - обновляется автоматически каждые 2 секунды.

## UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│ [Refresh] [Clear All]                    Traces: 15          │
├─────────────────┬───────────────────────────────────────────┤
│ Trace List      │ Trace Details                             │
│                 │                                             │
│ [12:34:56] gem. │ ┌─ Overview ─────────────────────────────┐│
│ | 1234ms ✓      │ │ Model: gemini-3-flash-preview          ││
│                 │ │ Thinking Level: low                     ││
│ [12:34:50] gem. │ │ Latency: 1234.56ms                     ││
│ | 2345ms        │ │ Is Final: true                          ││
│                 │ │ ...                                      ││
│ [12:34:40] gem. │ └────────────────────────────────────────┘│
│ | 1500ms ❌     │ ┌─ System Prompt ─────────────────────────┐│
│                 │ │ You are a helpful assistant...          ││
│                 │ └────────────────────────────────────────┘│
│                 │ ┌─ User Input ────────────────────────────┐│
│                 │ │ What is in this document?               ││
│                 │ └────────────────────────────────────────┘│
│                 │ ┌─ Input Files ───────────────────────────┐│
│                 │ │ [{"uri": "https://..."}]                ││
│                 │ └────────────────────────────────────────┘│
│                 │ ┌─ Response JSON ─────────────────────────┐│
│                 │ │ {                                        ││
│                 │ │   "assistant_text": "...",              ││
│                 │ │   "actions": [...],                     ││
│                 │ │   "is_final": true                      ││
│                 │ │ }                                        ││
│                 │ └────────────────────────────────────────┘│
│                 │ ┌─ Parsed Actions ────────────────────────┐│
│                 │ │ [{"type": "final", "payload": {}}]      ││
│                 │ └────────────────────────────────────────┘│
│                 │ ┌─ Errors ────────────────────────────────┐│
│                 │ │ No errors                                ││
│                 │ └────────────────────────────────────────┘│
│                 │                                             │
│                 │ [Copy Request JSON] [Copy Response JSON]   │
└─────────────────┴───────────────────────────────────────────┘
```

## Trace List (Left Panel)

### Format
```
[HH:MM:SS] model | latency final? error?
```

**Examples:**
- `[12:34:56] gemini-3-flash-preview | 1234ms ✓` - successful final response
- `[12:34:50] gemini-3-flash-preview | 2345ms` - intermediate response
- `[12:34:40] gemini-3-flash-preview | 1500ms ❌` - error (shown in red)

### Indicators
- **✓** - is_final=true (last response in conversation turn)
- **❌** - errors occurred
- **Red text** - trace has errors

### Sorting
- Newest traces at top (DESC by timestamp)
- Auto-updates every 2 seconds

## Trace Details (Right Panel)

### Sections

#### 1. Overview
```
Model: gemini-3-flash-preview
Thinking Level: low
Conversation ID: uuid
Trace ID: uuid
Timestamp: 2025-01-01T12:34:56.789Z
Latency: 1234.56ms
Is Final: true
Input Files Count: 2
```

#### 2. System Prompt
Full system prompt sent to model. Read-only.

#### 3. User Input
User text/question sent to model.

#### 4. Input Files
JSON array of file URIs attached to request:
```json
[
  {"uri": "https://generativelanguage.googleapis.com/v1beta/files/abc123"},
  {"uri": "https://generativelanguage.googleapis.com/v1beta/files/xyz789"}
]
```

#### 5. Response JSON
Raw JSON response from Gemini:
```json
{
  "assistant_text": "Based on the document...",
  "actions": [
    {
      "type": "request_roi",
      "payload": {"image_ref": "...", "hint_text": "..."},
      "note": "Need table data"
    }
  ],
  "is_final": false
}
```

#### 6. Parsed Actions
Extracted actions array (same as in Response JSON but formatted):
```json
[
  {
    "type": "request_roi",
    "payload": {"image_ref": "item-123", "hint_text": "Select table"},
    "note": "Need table data"
  }
]
```

#### 7. Errors
If errors occurred during request/response:
```
API Error: Rate limit exceeded
```

Background color: light red if errors exist.

## Actions

### Refresh Button
Manually refresh trace list (also auto-refreshes every 2s).

### Clear All Button
Clear all traces from memory. **Warning:** Cannot undo.

### Copy Request JSON
Copy request data to clipboard:
```json
{
  "model": "gemini-3-flash-preview",
  "system_prompt": "...",
  "user_text": "...",
  "file_uris": ["..."],
  "thinking_level": "low"
}
```

**Use case:** Replay request in external tool, debug, share.

### Copy Response JSON
Copy raw response JSON to clipboard.

**Use case:** Analyze structured output, debug parsing, share.

## How Tracing Works

### 1. Trace Creation
When `Agent.ask()` is called:
```python
trace = ModelTrace(
    conversation_id=...,
    model=...,
    thinking_level=...,
    system_prompt=SYSTEM_PROMPT,
    user_text=user_text,
    input_files=[{"uri": uri} for uri in file_uris],
)
```

### 2. Timing
```python
start_time = time.perf_counter()
# ... call Gemini ...
latency_ms = (time.perf_counter() - start_time) * 1000
```

### 3. Response Capture
```python
trace.response_json = result_dict  # Raw JSON
trace.parsed_actions = [...]  # Extracted actions
trace.latency_ms = latency_ms
trace.is_final = reply.is_final
```

### 4. Error Capture
```python
except Exception as e:
    trace.errors.append(str(e))
    trace.latency_ms = ...
```

### 5. Storage
```python
trace_store.add(trace)  # Add to in-memory store
```

### 6. Message Persistence
```python
await supabase_repo.qa_add_message(
    ...,
    meta={
        ...,
        "trace_id": trace.id,  # Link to trace
    }
)
```

## TraceStore

### Configuration
```python
TraceStore(maxsize=200)  # Keep last 200 traces
```

### Implementation
- Uses `collections.deque` with `maxlen`
- Automatic LRU eviction (oldest traces removed when full)
- In-memory only (not persisted to DB)

### Methods
```python
trace_store.add(trace)           # Add trace
trace_store.list()                # Get all (newest first)
trace_store.get(trace_id)        # Get by ID
trace_store.clear()               # Clear all
trace_store.count()               # Get count
```

## Use Cases

### 1. Debug Structured Output
**Problem:** Model returning invalid JSON or unexpected actions.

**Solution:**
1. Open Inspector
2. Find trace for problematic request
3. Check "Response JSON" - is it valid?
4. Check "Parsed Actions" - are actions correct?
5. Copy Response JSON → test in JSON validator

### 2. Optimize Performance
**Problem:** Slow responses.

**Solution:**
1. Open Inspector
2. Sort by latency (look at ms column)
3. Check "Input Files Count" - too many files?
4. Check "User Input" - prompt too long?
5. Adjust file selection or simplify prompts

### 3. Debug ROI Workflow
**Problem:** ROI not triggering correctly.

**Solution:**
1. Ask question → expect request_roi action
2. Open Inspector
3. Check "Parsed Actions" - is request_roi present?
4. Check "Response JSON" - payload correct?
5. If missing, check "System Prompt" - clear instructions?

### 4. Analyze Model Behavior
**Problem:** Model gives inconsistent answers.

**Solution:**
1. Ask same question multiple times
2. Open Inspector
3. Compare "Response JSON" across traces
4. Check "Latency" - correlation with quality?
5. Check "Thinking Level" - low vs high difference?

### 5. Share Debug Info
**Problem:** Need to report issue to team.

**Solution:**
1. Find problematic trace
2. Click "Copy Request JSON"
3. Paste in bug report / chat
4. Click "Copy Response JSON"
5. Paste in bug report / chat
6. Team can reproduce/analyze without access to app

## Example Workflow

### Scenario: Model not requesting ROI

**Step 1:** Ask question about document
```
User: "What's in the table on page 1?"
```

**Step 2:** Expect ROI request, but model gives generic answer

**Step 3:** Open Model Inspector

**Step 4:** Select latest trace

**Step 5:** Check "Parsed Actions"
```json
[
  {"type": "answer", "payload": {}, "note": null}
]
```

**Expected:** `{"type": "request_roi", ...}`

**Step 6:** Check "System Prompt"
```
You are a helpful assistant...
```

**Issue found:** System prompt doesn't mention ROI capability!

**Step 7:** Update `SYSTEM_PROMPT` in `app/services/agent.py`:
```python
SYSTEM_PROMPT = """...
- Если нужен ROI (region of interest) — верни action "request_roi" с описанием области.
..."""
```

**Step 8:** Test again → ROI works!

## Auto-Refresh

Inspector window auto-refreshes every 2 seconds:
```python
QTimer.timeout.connect(self._refresh_list)
timer.start(2000)
```

**Benefits:**
- See new traces appear automatically
- Don't need to click Refresh manually
- Keep window open while working

**Note:** Auto-refresh preserves current selection (doesn't jump around).

## Performance

### Memory Usage
- Each trace: ~1-10 KB (depends on response size)
- 200 traces: ~2 MB max
- Automatic eviction keeps memory bounded

### UI Performance
- List updates: O(n) where n = trace count
- Auto-refresh every 2s: negligible overhead
- Large JSON rendering: handled by QTextEdit

### Optimization Tips
1. Reduce `maxsize` if memory constrained: `TraceStore(maxsize=50)`
2. Clear traces periodically: Click "Clear All"
3. Close Inspector when not needed

## Limitations (MVP)

### Not Implemented
- ❌ Persist traces to database
- ❌ Search/filter traces
- ❌ Export traces to file
- ❌ Replay trace (resend request)
- ❌ Compare two traces side-by-side
- ❌ Trace visualization (timeline/graph)

### Workarounds
- **Search:** Use Copy JSON + external text editor search
- **Export:** Copy JSON → save manually
- **Replay:** Copy Request JSON → implement custom script

## Troubleshooting

### "No traces shown"
- **Check:** Have you asked any questions?
- **Check:** Click "Refresh" button
- **Check:** `trace_store` initialized in MainWindow?

### "Trace details empty"
- **Check:** Did you click on a trace in the list?
- **Check:** Trace has data (not just created)?

### "Copy buttons disabled"
- **Check:** Select a trace first
- **Check:** Trace has response_json (not error-only trace)

### "Auto-refresh not working"
- **Check:** Window is visible (not minimized)
- **Check:** QTimer running (should be automatic)

### "Latency seems wrong"
- **Check:** Includes full round-trip (request + response)
- **Note:** Network latency included
- **Note:** First request may be slower (cold start)

## Summary

Model Inspector предоставляет:
- ✅ Полную видимость вызовов модели
- ✅ Детали промптов, файлов, ответов
- ✅ Тайминги для оптимизации
- ✅ Ошибки для отладки
- ✅ Copy JSON для sharing
- ✅ Auto-refresh для удобства

Essential tool для:
- 🐛 Debugging structured output
- ⚡ Performance optimization
- 🔍 Understanding model behavior
- 📤 Sharing debug info with team

Open it, keep it open, use it! 🚀
