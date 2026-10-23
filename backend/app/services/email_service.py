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


def account_exists_email(to: str, name: str, login_link: str, reset_link: str) -> Email:
    """Sent when someone signs up with an email that already has an account."""
    safe_name = html.escape(name)
    return Email(
        to=to,
        subject="You already have a TrustShare account",
        text=(
            f"Hi {name},\n\n"
            "Someone tried to create a TrustShare account with this email address, but you "
            "already have one.\n\n"
            f"If it was you, just log in: {login_link}\n"
            f"Forgot your password? Reset it here: {reset_link}\n\n"
            "If it wasn't you, you can ignore this email – nothing has changed.\n"
        ),
        html=_layout(
            "You already have an account",
            f"<p>Hi {safe_name},</p><p>Someone tried to create a TrustShare account with this "
            "email address, but you already have one. If it was you, just log in. "
            f'Forgot your password? <a href="{html.escape(reset_link)}">Reset it here</a>.</p>',
            "Log in",
            login_link,
            "If it wasn't you, you can ignore this email – nothing has changed.",
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


def file_shared_email(
    to: str,
    name: str,
    owner_name: str,
    owner_email: str,
    file_name: str,
    can_download: bool,
    expires: str | None,
    link: str,
) -> Email:
    """Tells a registered user that a file was shared with them. Contains no file content – the
    file itself only opens after they log in."""
    access = "view and download" if can_download else "view (preview only)"
    until = f" until {expires}" if expires else ""
    safe = {
        k: html.escape(v)
        for k, v in {
            "name": name,
            "owner": owner_name,
            "file": file_name,
            "email": owner_email,
        }.items()
    }
    return Email(
        to=to,
        subject=f'{owner_name} shared "{file_name}" with you on TrustShare',
        text=(
            f"Hi {name},\n\n"
            f'{owner_name} ({owner_email}) shared the file "{file_name}" with you.\n'
            f"You can {access}{until}.\n\n"
            f'Open it under "Shared with me" after logging in:\n{link}\n\n'
            "Not expecting this? You can ignore this email; the owner can revoke access any time.\n"
        ),
        html=_layout(
            "A file was shared with you",
            f"<p>Hi {safe['name']},</p><p><strong>{safe['owner']}</strong> ({safe['email']}) "
            f"shared the file <strong>{safe['file']}</strong> with you. You can {access}{until}."
            "</p><p>The file stays encrypted on TrustShare and opens after you log in.</p>",
            "Open Shared with me",
            link,
            "Not expecting this? You can ignore this email; the owner can revoke access any time.",
        ),
    )
