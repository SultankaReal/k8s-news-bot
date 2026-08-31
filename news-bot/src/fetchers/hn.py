"""HackerNews fetcher — filters by Kubernetes/DevOps keywords."""
import logging
from datetime import datetime, timezone, timedelta

import requests

from . import Article

log = logging.getLogger(__name__)

KEYWORDS = [
    "kubernetes", "k8s", "devops", "helm", "prometheus",
    "grafana", "argocd", "cilium", "ebpf", "opentelemetry",
    "managed kubernetes", "eks", "gke", "aks", "mk8s",
    "monitoring", "observability", "service mesh", "istio",
]

HN_SEARCH = "https://hn.algolia.com/api/v1/search"


def fetch(hours: int = 6, min_points: int = 10) -> list[Article]:
    cutoff = int((datetime.utcnow() - timedelta(hours=hours)).timestamp())
    articles: list[Article] = []

    for kw in KEYWORDS[:8]:
        try:
            resp = requests.get(
                HN_SEARCH,
                params={
                    "query": kw,
                    "tags": "story",
                    "numericFilters": f"created_at_i>{cutoff},points>{min_points}",
                    "hitsPerPage": 5,
                },
                timeout=10,
            )
            resp.raise_for_status()
            for hit in resp.json().get("hits", []):
                url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}"
                articles.append(
                    Article(
                        url=url,
                        title=hit.get("title", ""),
                        source="news.ycombinator.com",
                        published=datetime.fromtimestamp(
                            hit["created_at_i"], tz=timezone.utc
                        ),
                        summary=f"HN: {hit.get('points', 0)} pts · {hit.get('num_comments', 0)} comments",
                        tags=["hackernews", kw.replace(" ", "-")],
                    )
                )
        except Exception as exc:
            log.warning("HN kw=%r: %s", kw, exc)

    # deduplicate by URL
    seen: set[str] = set()
    unique = []
    for a in articles:
        if a.url not in seen:
            seen.add(a.url)
            unique.append(a)

    log.info("HackerNews: %d unique articles", len(unique))
    return unique
