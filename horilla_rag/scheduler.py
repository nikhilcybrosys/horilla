"""APScheduler background jobs for RAG embedding maintenance."""

import sys

from django.conf import settings


def start_scheduler():
    """Start background scheduler for RAG batch jobs."""
    skip_commands = ["makemigrations", "migrate", "compilemessages", "flush", "shell"]
    if any(cmd in sys.argv for cmd in skip_commands):
        return

    try:
        import pytz
        from apscheduler.schedulers.background import BackgroundScheduler

        from horilla_rag.services.batch_jobs import reindex_attendance_summaries

        scheduler = BackgroundScheduler(
            timezone=pytz.timezone(getattr(settings, "TIME_ZONE", "UTC"))
        )

        # Nightly at 2 AM: re-index attendance summaries
        scheduler.add_job(
            reindex_attendance_summaries,
            "cron",
            hour=2,
            minute=0,
            id="rag_reindex_attendance",
            replace_existing=True,
            misfire_grace_time=3600 * 4,
        )

        # Daily at 6 AM: generate proactive insight alerts
        def generate_daily_insights():
            from horilla_rag.services.insights_service import InsightsService

            InsightsService().generate_all()

        scheduler.add_job(
            generate_daily_insights,
            "cron",
            hour=6,
            minute=0,
            id="rag_daily_insights",
            replace_existing=True,
            misfire_grace_time=3600 * 4,
        )

        scheduler.start()

    except Exception as e:
        import logging

        logging.getLogger(__name__).warning(f"RAG scheduler failed to start: {e}")
