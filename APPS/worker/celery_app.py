"""
Celery application factory.
Broker: Redis
Result backend: Redis
Beat schedule: cron workflows + usage rollup
"""
import os
import sys

# Worker shares api/ codebase — add it to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from celery import Celery
from celery.schedules import crontab

from core.config import settings

celery_app = Celery(
    "cat_ai_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "tasks.ingestion",
        "tasks.memory",
        "tasks.workflow_exec",
        "tasks.summarize",
        "tasks.usage_rollup",
        "tasks.notifications",
    ],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Reliability
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Result expiry
    result_expires=60 * 60 * 24,  # 24 hours
    # Retry defaults
    task_max_retries=3,
    task_default_retry_delay=30,
    # Dead-letter queue — tasks that exhaust retries go here
    task_routes={
        "tasks.workflow_exec.*": {"queue": "workflows"},
        "tasks.ingestion.*": {"queue": "ingestion"},
        "tasks.memory.*": {"queue": "memory"},
        "tasks.notifications.*": {"queue": "notifications"},
        "tasks.summarize.*": {"queue": "summarize"},
        "tasks.usage_rollup.*": {"queue": "usage"},
    },
    # Beat schedule (cron jobs)
    beat_schedule={
        # Roll up usage stats and push to Stripe every hour
        "usage-rollup-hourly": {
            "task": "tasks.usage_rollup.rollup_usage",
            "schedule": crontab(minute=0),  # top of every hour
        },
        # Check for cron-triggered workflows every minute
        "cron-workflows-tick": {
            "task": "tasks.workflow_exec.run_cron_workflows",
            "schedule": crontab(),  # every minute
        },
    },
)


if __name__ == "__main__":
    celery_app.start()