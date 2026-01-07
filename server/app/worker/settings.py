"""arq worker settings"""

from arq.connections import RedisSettings

from app.config import settings
from app.worker.tasks import process_llm_job, startup, shutdown


class WorkerSettings:
    """arq worker configuration"""

    redis_settings = RedisSettings(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password or None,
        database=settings.redis_db,
    )

    functions = [process_llm_job]

    on_startup = startup
    on_shutdown = shutdown

    max_jobs = settings.worker_max_jobs
    job_timeout = settings.worker_job_timeout

    max_tries = settings.worker_max_retries
    retry_jobs = True

    health_check_interval = 30
    queue_name = "arq:llm_jobs"
