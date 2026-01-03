# Использование промтов

## Как это работает

### 1. Создание промта

В диалоге управления промтами создайте промт с:
- **Title**: название промта
- **System Prompt**: системный промт для модели (инструкции для AI)
- **User Text**: шаблон пользовательского запроса с плейсхолдерами

### 2. Плейсхолдеры в User Text

Используйте следующие плейсхолдеры:
- `{question}` - вопрос пользователя из поля ввода
- `{context_catalog_json}` - JSON каталог доступных файлов/кропов

#### Пример User Text:
```
Вопрос пользователя:
{question}

context_catalog (используй только эти id; если нужен кроп — запроси через request_files):
{context_catalog_json}

Требование:
- Если можно ответить по тексту — ответь сразу.
- Если нужны чертежи/размеры — запроси конкретные context_item_id кропов.
```

### 3. Применение промта в чате

1. В ChatPanel выберите промт из выпадающего списка
2. **System prompt** автоматически применится к запросу
3. **User text** используется как шаблон (НЕ отображается в поле ввода)
4. Поле ввода остается **пустым** для вашего вопроса
5. Введите ваш вопрос
6. При отправке:
   - Ваш вопрос подставляется в `{question}`
   - Каталог файлов подставляется в `{context_catalog_json}`
   - Построенный промт отправляется модели вместе с system_prompt

### 4. Редактирование промта

- Нажмите кнопку ✏️ рядом с селектором промтов
- Откроется диалог редактирования выбранного промта

## Технические детали

### Обработка в коде

1. **ChatPanel** (`_on_prompt_changed`):
   ```python
   self._current_system_prompt = prompt.get("system_prompt", "")
   self._current_user_text_template = prompt.get("user_text", "")
   self.input_field.clear()  # Поле остается пустым
   ```

2. **ChatPanel** (`_on_send`):
   ```python
   self.askModelRequested.emit(
       text,  # Вопрос пользователя
       system_prompt,  # System prompt
       user_text_template,  # Шаблон с плейсхолдерами
       model_name, thinking_level, thinking_budget, file_refs
   )
   ```

3. **MainWindowHandlers** (`_run_agentic`):
   ```python
   user_prompt = build_user_prompt(
       question,  # Вопрос пользователя
       context_catalog_json,  # JSON каталог
       user_text_template  # Шаблон из промта
   )
   ```

4. **Agent** (`build_user_prompt`):
   ```python
   if user_text_template and "{question}" in user_text_template:
       return user_text_template.format(
           question=question,
           context_catalog_json=context_catalog_json,
       )
   # Иначе используется дефолтный шаблон
   ```

### База данных

Таблица `user_prompts`:
- `id` - UUID промта
- `client_id` - идентификатор клиента
- `title` - название промта
- `system_prompt` - системный промт
- `user_text` - шаблон с плейсхолдерами
- `r2_key` - ключ в R2 для полного содержимого
- `created_at`, `updated_at` - временные метки

## Примеры промтов

### Промт 1: Детальный анализ чертежей
**System Prompt:**
```
Ты — эксперт по техническим чертежам. Анализируй размеры и спецификации внимательно.
```

**User Text:**
```
Вопрос: {question}

Доступный контекст:
{context_catalog_json}

Если нужны дополнительные чертежи — запроси через request_files.
```

### Промт 2: Быстрый поиск
**System Prompt:**
```
Отвечай кратко и по делу.
```

**User Text:**
```
{question}

Контекст: {context_catalog_json}
```

### Промт 3: Без шаблона (простой вопрос)
**System Prompt:**
```
Ты — помощник по документации.
```

**User Text:**
```
{question}
```
(Без `{context_catalog_json}` - для простых вопросов без контекста)
