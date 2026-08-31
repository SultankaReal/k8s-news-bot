"""Entry point — initialises DB, registers APScheduler jobs, blocks."""
import logging
import os
import signal
import sys
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import get_config
from .state.db import init_db
from .scheduler import daily_digest, weekly_report, cleanup_gptr_outputs

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


def main() -> None:
    cfg = get_config()
    log.info("k8s-news-bot starting up")

    init_db()
    log.info("State DB initialised at %s", cfg.db_path)

    scheduler = BlockingScheduler(timezone="UTC")

    # Daily digest
    daily_cron = cfg.daily_digest_cron  # e.g. "0 6 * * *" = 09:00 MSK
    scheduler.add_job(
        daily_digest,
        CronTrigger.from_crontab(daily_cron),
        id="daily_digest",
        name="Daily K8s/DevOps digest",
        misfire_grace_time=300,
        coalesce=True,
    )
    log.info("Daily digest scheduled: %s UTC", daily_cron)

    # Weekly deep research report
    weekly_cron = cfg.weekly_report_cron  # e.g. "0 7 * * 1" = Monday 10:00 MSK
    scheduler.add_job(
        weekly_report,
        CronTrigger.from_crontab(weekly_cron),
        id="weekly_report",
        name="Weekly deep research report",
        misfire_grace_time=600,
        coalesce=True,
    )
    log.info("Weekly report scheduled: %s UTC", weekly_cron)

    # Daily cleanup of old gptr output files (runs at 03:00 UTC)
    scheduler.add_job(
        cleanup_gptr_outputs,
        CronTrigger.from_crontab("0 3 * * *"),
        id="cleanup_outputs",
        name="Cleanup old gptr outputs",
        misfire_grace_time=3600,
        coalesce=True,
    )
    log.info("Cleanup job scheduled: 0 3 * * * UTC")

    # Run immediately on startup if env var set (useful for testing)
    if os.environ.get("RUN_DAILY_NOW") == "1":
        log.info("RUN_DAILY_NOW=1 — running daily digest immediately")
        daily_digest()

    if os.environ.get("RUN_WEEKLY_NOW") == "1":
        log.info("RUN_WEEKLY_NOW=1 — running weekly report immediately")
        weekly_report()

    def _shutdown(sig, _frame):
        log.info("Received signal %s — shutting down", sig)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    log.info("Scheduler started. Jobs: %s", [j.name for j in scheduler.get_jobs()])
    scheduler.start()


if __name__ == "__main__":
    main()
