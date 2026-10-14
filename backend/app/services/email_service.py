"""Sending email through Gmail SMTP (STARTTLS on port 587, login with an app password).

If SMTP isn't configured (no SMTP_USER / SMTP_PASSWORD), the email is written to the backend log
instead – handy on a laptop and in CI, and nothing breaks.

Emails are sent as a FastAPI *background task*, after the response has gone out:
  - the user doesn't wait for Gmail
  - "email exists" and "email doesn't exist" take the same time (no leak of who is registered)
"""

import html
import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str
    html: str


class EmailSender:
    def send(self, email: Email) -> None:
        settings = get_settings()
        password = settings.smtp_password.get_secret_value()
        if not settings.smtp_user or not password:
            logger.warning(
                "SMTP not configured – email NOT sent. To: %s | Subject: %s\n%s",
                email.to,
                email.subject,
                email.text,
            )
            return

        message = EmailMessage()
        message["From"] = formataddr((settings.mail_from_name, settings.smtp_user))
        message["To"] = email.to
        message["Subject"] = email.subject
        message.set_content(email.text)  # plain-text version for simple mail clients
        message.add_alternative(email.html, subtype="html")

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
                smtp.starttls(context=ssl.create_default_context())  # encrypt before logging in
                smtp.login(settings.smtp_user, password)
                smtp.send_message(message)
            logger.info("Email sent to %s: %s", email.to, email.subject)
        except (smtplib.SMTPException, OSError):
            # Runs in the background, so the user already got their answer; just record it.
            logger.exception("Could not send email to %s", email.to)


def get_email_sender() -> EmailSender:
    """FastAPI dependency (tests replace it with one that just collects the emails)."""
    return EmailSender()


# ---------- templates ----------


def _layout(title: str, body_html: str, button_text: str, link: str, footer: str) -> str:
    return f"""\
<div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;color:#1e293b">
  <p style="font-size:20px;font-weight:bold;color:#2563eb">TrustShare</p>
  <h2 style="font-size:18px">{title}</h2>
  {body_html}
  <p style="margin:28px 0">
    <a href="{html.escape(link)}" style="background:#2563eb;color:#fff;padding:12px 20px;
       border-radius:8px;text-decoration:none;font-weight:bold">{button_text}</a>
  </p>
  <p style="font-size:12px;color:#64748b">{footer}</p>
  <p style="font-size:12px;color:#64748b">If the button doesn't work, copy this link:<br>
    {html.escape(link)}</p>
</div>"""


def verification_email(to: str, name: str, link: str, hours: int) -> Email:
    safe_name = html.escape(name)
    return Email(
        to=to,
        subject="Verify your TrustShare email",
        text=(
            f"Hi {name},\n\n"
            "Welcome to TrustShare! Please confirm this is your email address by opening this "
            f"link within {hours} hours:\n\n{link}\n\n"
            "If you didn't create an account, you can ignore this email.\n"
        ),
        html=_layout(
            "Verify your email",
            f"<p>Hi {safe_name},</p><p>Welcome to TrustShare! Please confirm this is your email "
            f"address. The link works once and expires in {hours} hours.</p>",
            "Verify my email",
            link,
            "If you didn't create an account, you can ignore this email.",
        ),
    )


def password_reset_email(to: str, name: str, link: str, minutes: int) -> Email:
    safe_name = html.escape(name)
    return Email(
        to=to,
        subject="Reset your TrustShare password",
        text=(
            f"Hi {name},\n\n"
            f"Someone (hopefully you) asked to reset your TrustShare password.\n"
            f"Open this link within {minutes} minutes to choose a new one:\n\n{link}\n\n"
            "If you didn't ask for this, ignore this email – your password stays the same.\n"
        ),
        html=_layout(
            "Reset your password",
            f"<p>Hi {safe_name},</p><p>Someone (hopefully you) asked to reset your TrustShare "
            f"password. The link works once and expires in {minutes} minutes.</p>",
            "Choose a new password",
            link,
            "If you didn't ask for this, ignore this email – your password stays the same.",
        ),
    )
