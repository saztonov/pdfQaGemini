"""FastAPI server entry point"""

import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes import health, conversations, messages, jobs, files, prompts, auth
from app.services.redis_queue import init_redis_queue, get_redis_queue


def setup_logging():
    """Configure logging with file output"""
    # Create logs directory (use /logs in Docker, otherwise relative path)
    docker_logs = Path("/logs")
    logs_dir = docker_logs if docker_logs.exists() else Path(__file__).parent.parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / "server.log"

    # Configure handlers
    handlers = [
        logging.StreamHandler(),
        RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        ),
    ]

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )

    # Reduce httpx logging to avoid flooding console with polling requests
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    return logging.getLogger(__name__), log_file


logger, log_file_path = setup_logging()
logger.info(f"Логи сохраняются в: {log_file_path}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown"""
    logger.info("Starting pdfQaGemini server...")

    # Initialize Redis queue
    redis_queue = init_redis_queue()
    await redis_queue.connect()

    logger.info("Server started successfully")

    yield

    # Shutdown
    logger.info("Shutting down server...")
    await redis_queue.close()
    logger.info("Server stopped")


# Create FastAPI app
app = FastAPI(
    title="pdfQaGemini API",
    description="PDF Q&A with Gemini - Server API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    """Log all incoming requests"""
    logger.info(f">>> Incoming request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"<<< Response: {response.status_code}")
    return response

# Register routes
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(conversations.router, prefix="/api/v1/conversations", tags=["conversations"])
app.include_router(messages.router, prefix="/api/v1", tags=["messages"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["jobs"])
app.include_router(files.router, prefix="/api/v1/files", tags=["files"])
app.include_router(prompts.router, prefix="/api/v1/prompts", tags=["prompts"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])


if __name__ == "__main__":
    import uvicorn

    print(f"*** Starting uvicorn on {settings.host}:{settings.port} ***")
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,  # Disabled - causes issues on Windows
        log_level="info",
        access_log=True,
    )
