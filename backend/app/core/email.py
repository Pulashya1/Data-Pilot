"""Magic-link email delivery via stdlib `smtplib` (MASTER_PROMPT.md §9, §12 Phase 8) — no new
dependency, per the project's "ask before adding a library" rule (§13).

Only called when `Settings.smtp_host` is set. With it empty (the local-dev default),
`app/api/auth.py` never calls this at all — it returns the login link directly in its response
instead, so the whole login flow works with zero external setup.
"""

import smtplib
from email.message import EmailMessage

from app.core.config import Settings


def send_magic_link_email(settings: Settings, to_email: str, login_url: str) -> None:
    message = EmailMessage()
    message["Subject"] = "Your DataPilot sign-in link"
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message.set_content(
        "Sign in to DataPilot using the link below.\n\n"
        f"{login_url}\n\n"
        f"This link expires in {settings.auth_magic_link_ttl_minutes} minutes and can only be "
        "used once. If you didn't request this, you can ignore this email."
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)
