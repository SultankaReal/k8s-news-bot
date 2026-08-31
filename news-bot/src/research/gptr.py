"""GPT Researcher HTTP client.

API (from /openapi.json):
  POST /report/ with generate_in_background=False — synchronous, returns JSON with "report" field
"""
import logging
from typing import Optional

import requests

from ..config import get_config

log = logging.getLogger(__name__)

WEEKLY_QUERIES = [
    "Kubernetes upstream releases patch notes announcements August 2026 kubernetes.io github.com/kubernetes",
    "CNCF projects news August 2026: Helm Argo Cilium Flux Crossplane Kyverno Falco",
    "AWS EKS Google GKE Azure AKS managed Kubernetes releases updates August 2026",
    "Prometheus Grafana OpenTelemetry observability releases news August 2026",
    # Russian-language research (Habr, Yandex Cloud, VK Cloud, etc.)
    "Kubernetes DevOps Хабр новости контейнеры облако Яндекс август 2026",
]

DAILY_QUERY = (
    "Kubernetes upstream news August 2026: "
    "new releases patch notes official blog posts from kubernetes.io and github.com/kubernetes. "
    "Current supported Kubernetes versions only (1.30 and newer, released after 2024). "
    "Include: Kubernetes, CNCF, Helm, Argo, Cilium, container security from kubernetes.io. "
    "Exclude: OpenShift, Rancher, databases (PostgreSQL ClickHouse MySQL MongoDB Redis), "
    "old unsupported Kubernetes versions (1.23 1.24 1.25 1.26 1.27 1.28 1.29 and older)."
)


def research(query: str, timeout: Optional[int] = None) -> str:
    """
    Run a GPT Researcher task and return the report text.
    Uses synchronous mode — blocks until the report is ready.
    """
    cfg = get_config()
    base = cfg.gptr_url.rstrip("/")
    t = timeout or cfg.gptr_timeout

    payload = {
        "task": query,
        "report_type": "research_report",
        "report_source": "web",
        "tone": "Objective",
        "repo_name": "",
        "branch_name": "",
        "generate_in_background": False,
    }
    try:
        resp = requests.post(f"{base}/report/", json=payload, timeout=t)
        resp.raise_for_status()
        data = resp.json()
        report = data.get("report") or data.get("output") or ""
        log.info("gptr research done: query=%r len=%d", query[:60], len(report))
        return report
    except requests.Timeout:
        log.error("gptr research timed out after %ds: %r", t, query[:60])
        return ""
    except Exception as exc:
        log.error("gptr /report/ failed: %s", exc)
        return ""


def daily_research() -> str:
    """Quick daily research — single query."""
    return research(DAILY_QUERY, timeout=600)


def weekly_research() -> str:
    """Run all weekly queries and combine results."""
    results = []
    for query in WEEKLY_QUERIES:
        log.info("Weekly research: %s", query)
        text = research(query)
        if text:
            results.append(f"### {query}\n\n{text}\n")

    return "\n\n".join(results)
