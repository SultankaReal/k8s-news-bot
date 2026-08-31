"""GitHub trending repos and release notes fetcher."""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

from . import Article
from ..config import get_config

log = logging.getLogger(__name__)

K8S_TOPICS = [
    "kubernetes", "helm", "prometheus", "grafana",
    "argocd", "flux", "istio", "cilium", "keda",
    "opentelemetry", "ebpf", "falco",
]

TRACKED_REPOS = [
    "kubernetes/kubernetes",
    "prometheus/prometheus",
    "grafana/grafana",
    "argoproj/argo-cd",
    "fluxcd/flux2",
    "helm/helm",
    "cilium/cilium",
    "istio/istio",
    "open-telemetry/opentelemetry-collector",
]


def _headers() -> dict:
    cfg = get_config()
    h = {"Accept": "application/vnd.github.v3+json"}
    if cfg.github_token:
        h["Authorization"] = f"token {cfg.github_token}"
    return h


def fetch_trending(since_days: int = 1) -> list[Article]:
    """Return repos created/starred recently on given topics."""
    articles: list[Article] = []
    since = (datetime.utcnow() - timedelta(days=since_days)).strftime("%Y-%m-%d")

    for topic in K8S_TOPICS[:6]:  # limit API calls
        try:
            resp = requests.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": f"topic:{topic} created:>{since}",
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 3,
                },
                headers=_headers(),
                timeout=15,
            )
            resp.raise_for_status()
            for repo in resp.json().get("items", []):
                articles.append(
                    Article(
                        url=repo["html_url"],
                        title=f"[GitHub] {repo['full_name']} ⭐{repo['stargazers_count']}",
                        source="github.com",
                        summary=repo.get("description") or "",
                        tags=["github", topic],
                    )
                )
        except Exception as exc:
            log.warning("GitHub trending topic=%s: %s", topic, exc)

    return articles


def fetch_releases() -> list[Article]:
    """Fetch latest releases for tracked repos."""
    articles: list[Article] = []
    cutoff = datetime.utcnow() - timedelta(days=3)

    for repo in TRACKED_REPOS:
        try:
            resp = requests.get(
                f"https://api.github.com/repos/{repo}/releases/latest",
                headers=_headers(),
                timeout=10,
            )
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            data = resp.json()
            published = datetime.fromisoformat(
                data["published_at"].replace("Z", "+00:00")
            )
            if published.replace(tzinfo=None) < cutoff:
                continue
            articles.append(
                Article(
                    url=data["html_url"],
                    title=f"Release: {repo} {data['tag_name']}",
                    source="github.com/releases",
                    published=published,
                    summary=(data.get("body") or "")[:300],
                    tags=["release", "github"],
                )
            )
        except Exception as exc:
            log.warning("GitHub release %s: %s", repo, exc)

    log.info("GitHub: %d new releases", len(articles))
    return articles
