"""FastAPI server entry point"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes import health, conversations, messages, jobs, files, prompts
from app.services.job_processor import JobProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global job processor instance
job_processor: JobProcessor = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown"""
    global job_processor

    # Startup
    logger.info("Starting pdfQaGemini server...")

    # Initialize job processor
    job_processor = JobProcessor(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_key,
        gemini_api_key=settings.gemini_api_key,
        r2_public_base_url=settings.r2_public_base_url,
        r2_endpoint=settings.r2_endpoint,
        r2_bucket=settings.r2_bucket,
        r2_access_key=settings.r2_access_key,
        r2_secret_key=settings.r2_secret_key,
        poll_interval=settings.job_poll_interval,
    )
    await job_processor.start()

    logger.info("Server started successfully")

    yield

    # Shutdown
    logger.info("Shutting down server...")
    await job_processor.stop()
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

# Register routes
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(conversations.router, prefix="/api/v1/conversations", tags=["conversations"])
app.include_router(messages.router, prefix="/api/v1", tags=["messages"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["jobs"])
app.include_router(files.router, prefix="/api/v1/files", tags=["files"])
app.include_router(prompts.router, prefix="/api/v1/prompts", tags=["prompts"])


def get_job_processor() -> JobProcessor:
    """Get job processor instance for dependency injection"""
    return job_processor


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
