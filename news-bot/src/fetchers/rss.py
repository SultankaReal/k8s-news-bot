"""RSS/Atom feed fetcher for Kubernetes & DevOps sources."""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

import feedparser
import requests

from . import Article

log = logging.getLogger(__name__)

# ── Feed registry ────────────────────────────────────────────────────────────
#
# NOTE: several "official" blog RSS feeds (AWS containers, GKE blog,
# AKS TechCommunity, Alibaba Cloud) return HTML instead of RSS when
# requested from Russian IP addresses. We use GitHub release feeds as
# reliable alternatives for managed K8s providers.
#
FEEDS: list[dict] = [
    # Kubernetes official
    {"url": "https://kubernetes.io/feed.xml",
     "source": "kubernetes.io", "tags": ["kubernetes", "release"]},
    # CNCF
    {"url": "https://www.cncf.io/feed/",
     "source": "cncf.io", "tags": ["cncf", "cloud-native"]},
    # The New Stack
    {"url": "https://thenewstack.io/category/kubernetes/feed/",
     "source": "thenewstack.io", "tags": ["kubernetes"]},
    {"url": "https://thenewstack.io/category/devops/feed/",
     "source": "thenewstack.io", "tags": ["devops"]},
    # InfoQ
    {"url": "https://feed.infoq.com/kubernetes",
     "source": "infoq.com", "tags": ["kubernetes"]},
    {"url": "https://feed.infoq.com/devops",
     "source": "infoq.com", "tags": ["devops"]},

    # ── Managed Kubernetes providers ──────────────────────────────────────────
    # AWS EKS — GitHub release feeds (AWS blog times out from Russian IPs)
    {"url": "https://github.com/aws/eks-distro/releases.atom",
     "source": "github.com/aws/eks",
     "tags": ["aws", "eks", "release"]},
    {"url": "https://github.com/awslabs/amazon-eks-ami/releases.atom",
     "source": "github.com/aws/eks-ami",
     "tags": ["aws", "eks", "release"]},
    # Google GKE — official release notes feed
    {"url": "https://cloud.google.com/feeds/kubernetes-engine-release-notes.xml",
     "source": "cloud.google.com/gke",
     "tags": ["gke", "kubernetes", "release"]},
    # Azure AKS — GitHub releases (TechCommunity blog returns HTML from Russia)
    {"url": "https://github.com/Azure/AKS/releases.atom",
     "source": "github.com/Azure/AKS",
     "tags": ["aks", "azure", "kubernetes", "release"]},
    # Alibaba Cloud ACK — no reliable RSS from Russian IPs;
    # covered via GPT Researcher weekly query instead.
    # ─────────────────────────────────────────────────────────────────────────

    # Prometheus blog
    {"url": "https://prometheus.io/blog/feed.xml",
     "source": "prometheus.io", "tags": ["monitoring", "prometheus"]},
    # Grafana blog
    {"url": "https://grafana.com/blog/index.xml",
     "source": "grafana.com", "tags": ["monitoring", "grafana"]},

    # Habr — Russian tech community
    {"url": "https://habr.com/ru/rss/hub/kubernetes/posts/?fl=ru",
     "source": "habr.com", "tags": ["kubernetes", "ru"]},
    {"url": "https://habr.com/ru/rss/hub/devops/posts/?fl=ru",
     "source": "habr.com", "tags": ["devops", "ru"]},
    {"url": "https://habr.com/ru/rss/hub/monitoring/posts/?fl=ru",
     "source": "habr.com", "tags": ["monitoring", "ru"]},
    {"url": "https://habr.com/ru/rss/hub/cloud_computing/posts/?fl=ru",
     "source": "habr.com", "tags": ["cloud", "ru"]},
    {"url": "https://habr.com/ru/rss/hub/sys_admin/posts/?fl=ru",
     "source": "habr.com", "tags": ["sysadmin", "ru"]},
    {"url": "https://habr.com/ru/rss/hub/linux/posts/?fl=ru",
     "source": "habr.com", "tags": ["linux", "ru"]},
]


def _parse_date(entry) -> Optional[datetime]:
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = "k8s-news-bot/1.0 (+https://github.com)"
_FEED_TIMEOUT = 15  # seconds per feed


def fetch_all() -> list[Article]:
    articles: list[Article] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_feed, cfg): cfg for cfg in FEEDS}
        for fut in as_completed(futures):
            cfg = futures[fut]
            try:
                articles.extend(fut.result())
            except Exception as exc:
                log.warning("Feed %s failed: %s", cfg["url"], exc)
    log.info("RSS fetched %d articles from %d feeds", len(articles), len(FEEDS))
    return articles


def _strip_html(text: str) -> str:
    import re
    from html import unescape
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text).strip()


def _extract_title(entry, source: str) -> str:
    """Extract a human-readable title from an RSS entry.

    Habr company-blog posts have titles like 'Пост @user — Company (+N) — date'.
    In that case the real title is inside the first <strong> tag in the summary.
    """
    import re
    title = entry.get("title", "").strip()
    if source == "habr.com" and title.startswith("Пост @"):
        raw = entry.get("summary") or entry.get("description") or ""
        # Try <strong> first
        m = re.search(r"<strong[^>]*>(.+?)</strong>", raw, re.S)
        if m:
            candidate = _strip_html(m.group(1))
            if len(candidate) > 10:
                return candidate
        # Try first heading
        m = re.search(r"<h[1-3][^>]*>(.+?)</h[1-3]>", raw, re.S)
        if m:
            candidate = _strip_html(m.group(1))
            if len(candidate) > 10:
                return candidate
        # Fallback: first sentence of plain text (link roundup posts)
        plain = _strip_html(raw)
        first_sent = re.split(r"[.!?]\s", plain[:300])[0].strip()
        if len(first_sent) > 10:
            return first_sent[:100]
    return title


def _fetch_feed(cfg: dict) -> list[Article]:
    try:
        resp = _SESSION.get(cfg["url"], timeout=_FEED_TIMEOUT)
        resp.raise_for_status()
        # Reject HTML responses (bot-blocks, geo-redirects)
        ct = resp.headers.get("content-type", "")
        if "text/html" in ct:
            log.debug("Feed %s returned HTML (bot/geo-block) — skipping", cfg["url"])
            return []
        content = resp.content
    except Exception as exc:
        log.debug("Feed %s request failed: %s", cfg["url"], exc)
        return []

    parsed = feedparser.parse(content)
    if parsed.bozo and not parsed.entries:
        log.debug("Bozo feed %s: %s", cfg["url"], parsed.bozo_exception)
        return []

    result = []
    for entry in parsed.entries[:20]:
        url = entry.get("link", "")
        if not url:
            continue
        title = _extract_title(entry, cfg["source"])
        summary = entry.get("summary", entry.get("description", "")).strip()
        summary = _strip_html(summary)[:500]

        result.append(
            Article(
                url=url,
                title=title,
                source=cfg["source"],
                published=_parse_date(entry),
                summary=summary or None,
                tags=cfg.get("tags", []),
            )
        )
    return result
