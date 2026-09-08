"""Outbound email over SMTP.

The only thing that sends mail today is onboarding: when a platform admin
invites a tenant, or a tenant admin invites a user, the generated first-time
password is delivered here. Config lives in app/core/config.py (SMTP_*); no
other module reads those values.

`send_email` is a module-level function on purpose — tests monkeypatch it
directly (`monkeypatch.setattr("app.core.email.send_email", ...)`) rather
than standing up a fake SMTP server.
"""
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger("flowgard.email")


class EmailNotConfiguredError(RuntimeError):
    """Raised when a send is attempted but SMTP_HOST is unset. Routes translate
    this into a 503 so an operator knows the deployment is missing mail config
    rather than silently dropping an invite."""


def send_email(*, to: str, subject: str, body: str) -> None:
    """Send a plain-text email. Blocking; call from a request handler only for
    low-volume transactional mail like onboarding invites."""
    if not settings.smtp_host:
        raise EmailNotConfiguredError("SMTP_HOST is not set")

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)

    logger.info("sent %r email to %s", subject, to)
