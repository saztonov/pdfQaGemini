#!/bin/bash
# Git filter для предотвращения коммита секретов
# Использование: git config filter.secret.clean "bash .git-secret-filter.sh"

# Читаем stdin
content=$(cat)

# Проверяем на наличие подозрительных паттернов
if echo "$content" | grep -qiE "(api[_-]?key|secret[_-]?key|password|token|credentials).*[=:].*['\"]?[a-zA-Z0-9_-]{20,}"; then
    echo "❌ ВНИМАНИЕ: Обнаружены потенциальные секреты!" >&2
    echo "❌ Файл содержит API ключи, пароли или токены." >&2
    echo "❌ Коммит заблокирован для безопасности." >&2
    echo "" >&2
    echo "Если это ложное срабатывание, используйте:" >&2
    echo "  git commit --no-verify" >&2
    exit 1
fi

# Если проверка прошла, выводим содержимое без изменений
echo "$content"
