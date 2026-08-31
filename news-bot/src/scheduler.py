"""
APScheduler jobs:
 - daily_digest:  runs every day, RSS only (managed K8s + RU sources) — no LLM, no hallucination
 - weekly_report: runs every Monday, runs gptr deep research + delivers
"""
import logging
from datetime import datetime, timezone, timedelta

from .research import gptr
from .delivery import email as mailer

log = logging.getLogger(__name__)

# Russian sources to pull from RSS regardless of gptr
# Note: yandex.cloud blog RSS is broken (404); Habr covers YC content via cloud_computing hub
_RU_SOURCES = {"habr.com"}

# Habr topic filter — skip articles whose lead (before ":") contains these
# off-topic words but NO on-topic words (e.g. OTUS weekly DB digests)
_OFF_TOPIC_LEAD = frozenset([
    "postgresql", "clickhouse", "mysql", "mongodb", "redis", "rabbitmq",
    "playwright", "javascript", "typescript", "react", "angular",
    "swift", "kotlin", "ruby", " php",
])
_ON_TOPIC_LEAD = frozenset([
    "kubernetes", "k8s", "docker", "container", "контейнер",
    "helm", "devops", "ci/cd", "cicd", "облако", "cloud", "linux",
    "кластер", "cluster", "pod", "argo", "gitops", "terraform", "ansible",
    "kubectl", "мониторинг", "monitoring", "observability",
    "prometheus", "grafana", "инфраструктур", "infrastructure",
    "eks", "gke", "aks", "nginx", "сети", "network",
])


def _is_on_topic_ru(title: str) -> bool:
    """Return False only if the title lead has off-topic keywords and no on-topic ones."""
    lead = title.split(":")[0].lower()
    if any(w in lead for w in _OFF_TOPIC_LEAD):
        return any(w in lead for w in _ON_TOPIC_LEAD)
    return True
# Managed K8s providers — show in a dedicated daily section
# Using GitHub release feeds: AWS/GKE blogs block Russian IPs, GitHub does not
_MANAGED_K8S_SOURCES = {
    "AWS EKS Distro",   # EKS Distro releases (GitHub)
    "AWS EKS AMI",      # EKS AMI releases (GitHub)
    "GKE Release Notes",# GKE release notes (official feed)
    "Azure AKS",        # AKS releases (GitHub)
    # Alibaba ACK: no reliable RSS — covered via gptr weekly query
}
# Path where gptr writes output files (shared volume)
_GPTR_OUTPUTS_PATH = "/gptr-outputs"
# Articles no older than 96h for daily digest (Habr publishes less frequently)
_RU_MAX_AGE_H = 96
# Managed K8s blogs post less often — look back 120h (covers Thu-Mon gap on weekends)
_MANAGED_K8S_MAX_AGE_H = 120


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
        and _is_on_topic_ru(a.title)
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
        lines.append(f"**{art.title}**{pub} — {art.source}")
        if art.summary:
            snippet = art.summary[:200].rstrip()
            if len(art.summary) > 200:
                snippet += "…"
            lines.append(snippet)
        lines.append(art.url + "\n")

    return "\n".join(lines)


def _managed_k8s_section() -> str:
    """Fetch recent articles from managed K8s providers (EKS, GKE, AKS, ACK)."""
    from .fetchers.rss import fetch_all

    try:
        articles = fetch_all()
    except Exception as exc:
        log.warning("RSS fetch failed: %s", exc)
        return ""

    cutoff = datetime.now(timezone.utc) - timedelta(hours=_MANAGED_K8S_MAX_AGE_H)
    mk8s = [
        a for a in articles
        if a.source in _MANAGED_K8S_SOURCES
        and (a.published is None or a.published >= cutoff)
    ]

    if not mk8s:
        log.info("No recent managed K8s RSS articles (last %dh)", _MANAGED_K8S_MAX_AGE_H)
        return ""

    mk8s.sort(
        key=lambda a: a.published or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    log.info("Managed K8s RSS: %d articles", len(mk8s))
    lines = ["## ☁️ Managed Kubernetes (EKS · GKE · AKS · ACK)\n"]
    for art in mk8s[:12]:
        pub = f" ({art.published.strftime('%d.%m')})" if art.published else ""
        lines.append(f"**{art.title}**{pub} — {art.source}")
        if art.summary:
            snippet = art.summary[:450].rstrip()
            if len(art.summary) > 450:
                snippet += "…"
            lines.append(snippet)
        lines.append(art.url + "\n")

    return "\n".join(lines)


def daily_digest() -> None:
    log.info("=== daily_digest started ===")

    ru_section = _ru_rss_section()
    mk8s_section = _managed_k8s_section()

    if not ru_section and not mk8s_section:
        log.warning("daily_digest: all RSS sections empty — skipping")
        return

    date_str = datetime.utcnow().strftime("%d.%m.%Y")
    parts = [f"☸️ **K8s & DevOps дайджест — {date_str}**\n"]
    if mk8s_section:
        parts.append(mk8s_section)
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
