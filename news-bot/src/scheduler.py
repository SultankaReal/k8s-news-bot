"""
APScheduler jobs:
 - daily_digest:  runs every day, uses gptr quick search + RSS RU sources + delivers via email
 - weekly_report: runs every Monday, runs gptr deep research + delivers
"""
import logging
from datetime import datetime, timezone, timedelta

from .research import gptr
from .delivery import email as mailer

log = logging.getLogger(__name__)

# Russian sources to pull from RSS regardless of gptr
_RU_SOURCES = {"habr.com", "yandex.cloud"}
# Path where gptr writes output files (shared volume)
_GPTR_OUTPUTS_PATH = "/gptr-outputs"
# Articles no older than 96h for daily digest (Habr publishes less frequently)
_RU_MAX_AGE_H = 96


def _ru_rss_section() -> str:
    """Fetch recent articles from Russian sources (Habr, Yandex Cloud) via RSS."""
    from .fetchers.rss import fetch_all

    try:
        articles = fetch_all()
    except Exception as exc:
        log.warning("RSS fetch failed: %s", exc)
        return ""

    cutoff = datetime.now(timezone.utc) - timedelta(hours=_RU_MAX_AGE_H)
    ru = [
        a for a in articles
        if a.source in _RU_SOURCES
        and (a.published is None or a.published >= cutoff)
    ]

    if not ru:
        log.info("No recent Russian RSS articles (last %dh)", _RU_MAX_AGE_H)
        return ""

    ru.sort(
        key=lambda a: a.published or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    log.info("Russian RSS: %d articles from %s", len(ru), _RU_SOURCES)
    lines = ["## 🇷🇺 Свежее из российских источников\n"]
    for art in ru[:15]:
        pub = f" ({art.published.strftime('%d.%m')})" if art.published else ""
        lines.append(f"**{art.title}**{pub} — {art.source}\n{art.url}\n")

    return "\n".join(lines)


def daily_digest() -> None:
    log.info("=== daily_digest started ===")

    # Russian RSS: fast, no DDG dependency — fetch first
    ru_section = _ru_rss_section()

    # English research via gptr (takes 4-6 min)
    report = gptr.daily_research()

    if not report and not ru_section:
        log.warning("daily_digest: both gptr and RSS returned empty — skipping")
        return

    date_str = datetime.utcnow().strftime("%d.%m.%Y")
    parts = [f"☸️ **K8s & DevOps дайджест — {date_str}**\n"]
    if report:
        parts.append(report)
    if ru_section:
        parts.append(ru_section)

    full_text = "\n\n".join(parts)

    ok = mailer.deliver(full_text, subject=f"☸️ K8s & DevOps дайджест — {date_str}")
    if ok:
        log.info("Daily digest delivered")
    else:
        log.error("Daily digest delivery FAILED")


def cleanup_gptr_outputs() -> None:
    """Delete gptr .docx/.pdf/.json files older than GPTR_OUTPUTS_MAX_AGE_DAYS."""
    import os, time
    max_age = int(os.environ.get("GPTR_OUTPUTS_MAX_AGE_DAYS", "7"))
    cutoff = time.time() - max_age * 86400
    path = _GPTR_OUTPUTS_PATH
    if not os.path.isdir(path):
        log.debug("cleanup: outputs dir not found at %s, skipping", path)
        return
    removed = 0
    total_bytes = 0
    for fname in os.listdir(path):
        fpath = os.path.join(path, fname)
        if not os.path.isfile(fpath):
            continue
        mtime = os.path.getmtime(fpath)
        if mtime < cutoff:
            size = os.path.getsize(fpath)
            os.unlink(fpath)
            removed += 1
            total_bytes += size
    if removed:
        log.info("Cleanup: removed %d old gptr files (%.1f MB)", removed, total_bytes / 1e6)
    else:
        log.info("Cleanup: no old gptr files to remove (max_age=%dd)", max_age)


def weekly_report() -> None:
    log.info("=== weekly_report started ===")

    research_text = gptr.weekly_research()

    if not research_text:
        log.warning("weekly_report: gptr returned empty — skipping")
        return

    week_str = datetime.utcnow().strftime("неделя %W, %Y")
    header = f"📊 **Еженедельный аналитический дайджест — {week_str}**\n\n"
    full_text = header + research_text

    ok = mailer.deliver(full_text, subject=f"📊 K8s еженедельный дайджест — {week_str}")
    if ok:
        log.info("Weekly report delivered")
    else:
        log.error("Weekly report delivery FAILED")
