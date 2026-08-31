"""Central configuration — all settings from environment variables."""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    # ── Email delivery (Yandex SMTP) ────────────────────────────────────────
    email_from: str = field(
        default_factory=lambda: os.environ["EMAIL_FROM"]
    )
    email_password: str = field(
        default_factory=lambda: os.environ["EMAIL_PASSWORD"]
    )
    email_to: str = field(
        default_factory=lambda: os.environ.get("EMAIL_TO", os.environ["EMAIL_FROM"])
    )

    # ── LLM / Anthropic (not used by news-bot directly — kept for compat) ────
    anthropic_api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY")
    )
    anthropic_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "ANTHROPIC_BASE_URL", "https://api.anthropic.com"
        )
    )
    fast_model: str = field(
        default_factory=lambda: os.environ.get(
            "FAST_MODEL", "claude-haiku-4-5-20251001"
        )
    )
    smart_model: str = field(
        default_factory=lambda: os.environ.get("SMART_MODEL", "claude-sonnet-4-6")
    )

    # ── gptr-mcp research service ───────────────────────────────────────────
    gptr_url: str = field(
        default_factory=lambda: os.environ.get("GPTR_URL", "http://gptr:8000")
    )
    gptr_timeout: int = field(
        default_factory=lambda: int(os.environ.get("GPTR_TIMEOUT", "900"))
    )

    # ── Scheduling ──────────────────────────────────────────────────────────
    # Cron expressions (Moscow time = UTC+3, so offset accordingly)
    daily_digest_cron: str = field(
        default_factory=lambda: os.environ.get(
            "DAILY_DIGEST_CRON", "0 6 * * *"  # 09:00 MSK = 06:00 UTC
        )
    )
    weekly_report_cron: str = field(
        default_factory=lambda: os.environ.get(
            "WEEKLY_REPORT_CRON", "0 7 * * 1"  # Monday 10:00 MSK = 07:00 UTC
        )
    )

    # ── State / deduplication ────────────────────────────────────────────────
    db_path: str = field(
        default_factory=lambda: os.environ.get("DB_PATH", "/data/state.db")
    )

    # ── Fetch settings ───────────────────────────────────────────────────────
    max_articles_per_digest: int = field(
        default_factory=lambda: int(os.environ.get("MAX_ARTICLES", "10"))
    )
    article_ttl_days: int = field(
        default_factory=lambda: int(os.environ.get("ARTICLE_TTL_DAYS", "7"))
    )

    # ── GitHub ───────────────────────────────────────────────────────────────
    github_token: Optional[str] = field(
        default_factory=lambda: os.environ.get("GITHUB_TOKEN")
    )


# Singleton
_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
