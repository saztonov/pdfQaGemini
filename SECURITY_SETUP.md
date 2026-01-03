# 🔒 Настройка систем безопасности

## Быстрый старт

После клонирования репозитория выполните:

```bash
# 1. Установить pre-commit hooks
pip install pre-commit
pre-commit install

# 2. Настроить git фильтры (опционально)
bash .git-setup-filters.sh

# 3. Создать baseline для detect-secrets
detect-secrets scan > .secrets.baseline
```

## Что было настроено

### 1. `.gitattributes` ✅

**Автоматическая нормализация line endings:**
- Linux/Mac: LF (`\n`)
- Windows: CRLF (`\r\n`) только для `.bat`/`.cmd`
- Python, JSON, SQL: всегда LF

**Правильная обработка бинарных файлов:**
- Изображения: `.png`, `.jpg`, `.pdf`
- Архивы: `.zip`, `.tar`, `.gz`
- Python байткод: `.pyc`, `.pyo`

**Защита секретов:**
- Файлы `.env`, `*secret*`, `*password*` маркируются для проверки
- Автоматический фильтр перед коммитом

### 2. Pre-commit hooks (`.pre-commit-config.yaml`) ✅

Автоматические проверки перед каждым коммитом:

#### Базовые проверки
- ✓ Валидация YAML/JSON/TOML
- ✓ Проверка больших файлов (>5MB)
- ✓ Обнаружение private keys (SSH, SSL)
- ✓ Trailing whitespace
- ✓ Merge конфликты
- ✓ Python AST валидация

#### Сканирование секретов
- ✓ `detect-secrets` - API ключи, токены, пароли
- ✓ Baseline для whitelist известных false positives

#### Форматирование кода
- ✓ `black` - Python code formatter
- ✓ `ruff` - быстрый Python linter
- ✓ Автоматическое исправление проблем

#### Безопасность зависимостей
- ✓ `safety` - проверка уязвимостей в requirements.txt

#### Jupyter Notebooks
- ✓ `nbstripout` - очистка output перед коммитом

### 3. Git фильтры (`.git-secret-filter.sh`) ✅

Bash скрипт для блокировки коммитов с секретами:
- Паттерны: `api_key`, `secret_key`, `password`, `token`
- Блокирует если найдены значения 20+ символов
- Обход: `git commit --no-verify` (только если уверены!)

### 4. Security Policy (`SECURITY.md`) ✅

Документация по безопасности:
- Что делать при обнаружении уязвимости
- Как удалить секреты из git истории
- Хорошие практики работы с конфигурацией
- Checklist перед публикацией

## Установка и настройка

### Шаг 1: Установить зависимости

```bash
# Pre-commit framework
pip install pre-commit

# Инструменты безопасности
pip install detect-secrets safety

# Форматирование (опционально, если не установлены)
pip install black ruff

# Jupyter support (если используются notebooks)
pip install nbstripout
```

### Шаг 2: Активировать pre-commit

```bash
# Установить hooks в .git/hooks/
pre-commit install

# Проверка на всех файлах (первый раз)
pre-commit run --all-files
```

### Шаг 3: Создать baseline для detect-secrets

```bash
# Сканировать текущие файлы и создать baseline
detect-secrets scan > .secrets.baseline

# Проверить baseline
cat .secrets.baseline
```

Это создаст whitelist известных "секретов" (например, примеры в документации).

### Шаг 4: Настроить git фильтры (опционально)

```bash
# Автоматическая настройка
bash .git-setup-filters.sh

# Или вручную
git config filter.secret.clean "bash $(pwd)/.git-secret-filter.sh"
git config filter.secret.smudge cat
chmod +x .git-secret-filter.sh
```

## Использование

### Обычный workflow

```bash
# 1. Сделать изменения
vim my_file.py

# 2. Добавить в staging
git add my_file.py

# 3. Коммит - pre-commit автоматически запустится
git commit -m "Add feature"

# Pre-commit выполнит:
# - Форматирование black
# - Проверки ruff
# - Сканирование секретов
# - И другие проверки...

# 4. Если есть проблемы - они будут автоматически исправлены
# Добавить исправления и повторить коммит
git add -u
git commit -m "Add feature"
```

### Пропустить проверки (осторожно!)

```bash
# Пропустить только pre-commit hooks
git commit --no-verify -m "Emergency fix"

# Пропустить только определенный hook
SKIP=detect-secrets git commit -m "Fix with false positive"
```

### Обновить hooks

```bash
# Обновить версии hooks до последних
pre-commit autoupdate

# Переустановить hooks
pre-commit install --install-hooks
```

### Проверить конкретные файлы

```bash
# Один файл
pre-commit run --files my_file.py

# Все Python файлы
pre-commit run --files desktop/app/**/*.py

# Только black
pre-commit run black --all-files

# Только detect-secrets
pre-commit run detect-secrets --all-files
```

## Обработка false positives

### Если detect-secrets ложно срабатывает:

**Вариант 1: Обновить baseline**
```bash
# Пересканировать и обновить baseline
detect-secrets scan --baseline .secrets.baseline

# Commit новый baseline
git add .secrets.baseline
git commit -m "Update secrets baseline"
```

**Вариант 2: Inline pragma**
```python
# В коде добавить комментарий
API_KEY_EXAMPLE = "xxx-example-key"  # pragma: allowlist secret
```

**Вариант 3: Исключить файл**
```yaml
# В .pre-commit-config.yaml
- id: detect-secrets
  args: ['--baseline', '.secrets.baseline']
  exclude: 'docs/examples/.*'
```

## Проверка безопасности репозитория

### Сканировать историю git на секреты

```bash
# Использовать truffleHog
pip install truffleHog
trufflehog git file://. --json

# Или gitleaks
brew install gitleaks  # или скачать binary
gitleaks detect --source . --verbose
```

### Проверить зависимости

```bash
# Safety check
safety check -r requirements.txt

# Или через pip-audit
pip install pip-audit
pip-audit
```

### GitHub Secret Scanning

Если репозиторий на GitHub:
1. Settings → Security → Code security and analysis
2. Включить "Secret scanning"
3. Включить "Push protection"

## Troubleshooting

### Pre-commit падает на Windows

```bash
# Убедитесь что используете bash (Git Bash)
# Или измените shebang в скриптах на:
#!/usr/bin/env bash
```

### Hooks не запускаются

```bash
# Переустановить
pre-commit uninstall
pre-commit install

# Проверить что hooks есть
ls -la .git/hooks/pre-commit
```

### Black/ruff конфликтуют

```bash
# Обновить до совместимых версий
pip install --upgrade black ruff

# Проверить конфигурацию в pyproject.toml
cat desktop/pyproject.toml
```

### Detect-secrets слишком много срабатывает

```bash
# Повысить entropy порог
detect-secrets scan --baseline .secrets.baseline \
  --base64-limit 4.5 \
  --hex-limit 3.0
```

## Дополнительные инструменты

### GitGuardian (бесплатно для open source)

```bash
# Установка
pip install ggshield

# Scan
ggshield secret scan repo .
```

### Bandit (Python security linter)

Добавить в `.pre-commit-config.yaml`:
```yaml
- repo: https://github.com/PyCQA/bandit
  rev: 1.7.5
  hooks:
    - id: bandit
      args: ['-ll']  # Low severity и выше
```

### Trivy (сканер уязвимостей)

```bash
# Docker image
docker run aquasec/trivy fs .

# Binary
trivy fs .
```

## Checklist настройки (для новых разработчиков)

- [ ] Клонировать репозиторий
- [ ] Установить `pre-commit`: `pip install pre-commit`
- [ ] Активировать hooks: `pre-commit install`
- [ ] Запустить первую проверку: `pre-commit run --all-files`
- [ ] Создать `.secrets.baseline` (если нужно)
- [ ] Настроить git фильтры: `bash .git-setup-filters.sh`
- [ ] Прочитать `SECURITY.md`
- [ ] Настроить QSettings для конфигурации приложения
- [ ] Не использовать `.env` для секретов!

## Полезные ссылки

- [Pre-commit hooks](https://pre-commit.com/)
- [detect-secrets](https://github.com/Yelp/detect-secrets)
- [Black formatter](https://black.readthedocs.io/)
- [Ruff linter](https://docs.astral.sh/ruff/)
- [Git filter-repo](https://github.com/newren/git-filter-repo)
- [OWASP Cheat Sheet](https://cheatsheetseries.owasp.org/)

---

**Вопросы?** Создайте issue или свяжитесь с мейнтейнером.
