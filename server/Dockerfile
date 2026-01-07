FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (for caching)
COPY pyproject.toml .
RUN pip install --no-cache-dir -e . && \
    pip install --no-cache-dir watchfiles

# Copy source code
COPY . .

# Default command (overridden in docker-compose)
CMD ["python", "-m", "app.main"]
