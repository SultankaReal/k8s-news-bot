"""
Email delivery via Yandex SMTP.

SMTP settings:
  Server:  smtp.yandex.ru
  Port:    465 (SSL/TLS)
  Auth:    login + app-password (create at https://id.yandex.ru/security/app-passwords)
"""
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from ..config import get_config

log = logging.getLogger(__name__)


def _markdown_to_html(text: str) -> str:
    """Minimal Markdown → HTML conversion for email."""
    import re

    lines = text.split("\n")
    html_lines = []
    for line in lines:
        # Headers
        if line.startswith("## "):
            line = f"<h3>{line[3:]}</h3>"
        elif line.startswith("# "):
            line = f"<h2>{line[2:]}</h2>"
        else:
            # Bold **text**
            line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
            # Link 🔗 url
            line = re.sub(
                r"(https?://[^\s<>\"]+)",
                r'<a href="\1">\1</a>',
                line,
            )
            if line.strip():
                line = f"<p>{line}</p>"
            else:
                line = "<br>"
        html_lines.append(line)

    body = "\n".join(html_lines)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; font-size: 14px; color: #222; max-width: 700px; margin: 0 auto; padding: 20px; }}
  h2 {{ color: #1a56a0; }}
  h3 {{ color: #2070c0; border-bottom: 1px solid #ddd; padding-bottom: 4px; }}
  a {{ color: #1a56a0; }}
  p {{ margin: 6px 0; line-height: 1.5; }}
  .footer {{ margin-top: 24px; color: #888; font-size: 12px; border-top: 1px solid #eee; padding-top: 8px; }}
</style>
</head>
<body>
{body}
<div class="footer">k8s-news-bot · {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</div>
</body>
</html>"""


def send_email(subject: str, body: str, to_addr: str | None = None) -> bool:
    """Send digest email via Yandex SMTP."""
    cfg = get_config()
    smtp_user = cfg.email_from
    smtp_pass = cfg.email_password
    recipient = to_addr or cfg.email_to

    if not smtp_user or not smtp_pass or not recipient:
        log.error("Email: EMAIL_FROM / EMAIL_PASSWORD / EMAIL_TO not configured")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = recipient

    # Plain text fallback
    msg.attach(MIMEText(body, "plain", "utf-8"))
    # HTML version
    msg.attach(MIMEText(_markdown_to_html(body), "html", "utf-8"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.yandex.ru", 465, context=ctx, timeout=30) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [recipient], msg.as_bytes())
        log.info("Email sent to %s: %s", recipient, subject)
        return True
    except Exception as exc:
        log.error("Email send failed: %s", exc)
        return False


def deliver(text: str, subject: str | None = None) -> bool:
    """Deliver digest via email."""
    if not subject:
        today = datetime.utcnow().strftime("%d.%m.%Y")
        subject = f"☸️ K8s & DevOps дайджест — {today}"
    return send_email(subject, text)
