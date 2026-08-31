"""Claude API summarizer for daily digests."""
import logging
from datetime import datetime

import anthropic

from ..config import get_config
from ..fetchers import Article

log = logging.getLogger(__name__)


def _client() -> anthropic.Anthropic:
    cfg = get_config()
    return anthropic.Anthropic(
        api_key=cfg.anthropic_api_key,
        base_url=cfg.anthropic_base_url,
    )


def summarize_articles(articles: list[Article]) -> str:
    """Turn a list of articles into a concise Russian-language digest."""
    if not articles:
        return ""

    cfg = get_config()
    today = datetime.utcnow().strftime("%d.%m.%Y")

    # Build context block
    items_text = ""
    for i, a in enumerate(articles, 1):
        pub = a.published.strftime("%d.%m %H:%M") if a.published else "—"
        items_text += (
            f"{i}. [{a.source}] {a.title}\n"
            f"   URL: {a.url}\n"
            f"   Опубликовано: {pub}\n"
            f"   Краткое описание: {a.summary or 'нет'}\n\n"
        )

    prompt = f"""Ты — технический редактор дайджеста по теме Kubernetes, DevOps и мониторинг для команды разработчиков.

Вот список материалов за сегодня ({today}):

{items_text}

Задача: составь краткий дайджест на русском языке в формате для мессенджера.

Правила:
- Выбери 5-8 наиболее важных и интересных материалов
- Для каждого: одно предложение что это и почему важно
- Используй emoji для визуального разделения (☸️ kubernetes, 📊 monitoring, 🔧 devops, 🇷🇺 ru-source, 🚀 release)
- Сохраняй оригинальные URL — они важны
- Формат каждого пункта:
  <emoji> **Заголовок**
  Краткое пояснение (1-2 предложения)
  🔗 <url>

- В конце добавь строку с хэштегами: #kubernetes #devops #k8s #monitoring

Не добавляй вводных фраз типа "Вот дайджест" — сразу начинай с заголовка блока новостей."""

    try:
        msg = _client().messages.create(
            model=cfg.fast_model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as exc:
        log.error("Claude summarize failed: %s", exc)
        # Fallback: plain list
        lines = [f"☸️ K8s/DevOps дайджест — {today}\n"]
        for a in articles[:8]:
            lines.append(f"• **{a.title}**\n  {a.url}\n")
        return "\n".join(lines)


def summarize_weekly(research_text: str) -> str:
    """Format a weekly deep research report."""
    cfg = get_config()
    week = datetime.utcnow().strftime("неделя %W, %Y")

    prompt = f"""Ты — технический аналитик по теме Kubernetes, DevOps, Managed Kubernetes и мониторинг.

Вот результаты глубокого исследования за {week}:

{research_text[:6000]}

Задача: напиши структурированный еженедельный аналитический дайджест на русском языке.

Структура:
## 📋 Главное за неделю
(3-5 ключевых события/тренда)

## ☸️ Kubernetes & Cloud Native
(новости из CNCF-экосистемы)

## 🏗️ Managed Kubernetes
(EKS, GKE, AKS, Yandex Cloud MK8S — что нового)

## 📊 Мониторинг & Observability
(Prometheus, Grafana, OpenTelemetry и т.д.)

## 🔗 Стоит прочитать
(5 лучших материалов недели с URL)

Пиши кратко и по делу, без воды. Объём — до 2500 символов."""

    try:
        msg = _client().messages.create(
            model=cfg.smart_model,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as exc:
        log.error("Claude weekly report failed: %s", exc)
        return f"Еженедельный отчёт ({week})\n\n{research_text[:1000]}"
