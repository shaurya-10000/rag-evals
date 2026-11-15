import html
import logging

import httpx

from rag.config.settings import settings

logger = logging.getLogger("rag.mailer")

BREVO_URL = "https://api.brevo.com/v3/smtp/email"

_FONT = "font-family:-apple-system,Segoe UI,Roboto,sans-serif"
_BUTTON = "background:#059669;color:#fff;padding:12px 20px;border-radius:10px"
_BUTTON += ";text-decoration:none;font-weight:600"


def _link(path: str, token: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}{path}?token={token}"


def _render(heading: str, intro: str, button: str, url: str, outro: str) -> tuple[str, str]:
    safe_url = html.escape(url, quote=True)
    body = f"""\
<div style="{_FONT};max-width:480px;margin:0 auto;padding:24px;color:#171717">
  <h2 style="margin:0 0 16px">{html.escape(heading)}</h2>
  <p style="line-height:1.5">{html.escape(intro)}</p>
  <p style="margin:24px 0">
    <a href="{safe_url}" style="{_BUTTON}">{html.escape(button)}</a>
  </p>
  <p style="font-size:13px;color:#525252;line-height:1.5">{html.escape(outro)}</p>
  <p style="font-size:12px;color:#737373;word-break:break-all">
    If the button does not work, paste this link into your browser:<br>{safe_url}
  </p>
</div>"""
    text = f"{heading}\n\n{intro}\n\n{button}: {url}\n\n{outro}\n"
    return body, text


def send_email(to: str, subject: str, html_body: str, text_body: str) -> None:
    """Send through Brevo. Never raises: callers run this as a background task."""
    if not settings.BREVO_API_KEY or not settings.EMAIL_FROM_ADDRESS:
        if settings.is_production:
            logger.error("Email to %s not sent: BREVO_API_KEY/EMAIL_FROM_ADDRESS not set", to)
        else:
            logger.warning(
                "Brevo not configured, email not sent.\nTo: %s\nSubject: %s\n\n%s",
                to,
                subject,
                text_body,
            )
        return

    payload = {
        "sender": {"name": settings.EMAIL_FROM_NAME, "email": settings.EMAIL_FROM_ADDRESS},
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html_body,
        "textContent": text_body,
    }
    try:
        response = httpx.post(
            BREVO_URL,
            json=payload,
            headers={"api-key": settings.BREVO_API_KEY, "accept": "application/json"},
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to send email to %s", to)


def send_verification_email(to: str, username: str, token: str) -> None:
    html_body, text_body = _render(
        heading="Verify your email",
        intro=f"Hi {username}, confirm your email address to finish creating your account.",
        button="Verify email",
        url=_link("/verify-email", token),
        outro="This link expires in 24 hours. If you did not sign up, you can ignore this email.",
    )
    send_email(to, "Verify your email for RAG Evals", html_body, text_body)


def send_password_reset_email(to: str, username: str, token: str) -> None:
    html_body, text_body = _render(
        heading="Reset your password",
        intro=f"Hi {username}, we received a request to reset your password.",
        button="Choose a new password",
        url=_link("/reset-password", token),
        outro="This link expires in 30 minutes. If you did not ask for this, ignore this email.",
    )
    send_email(to, "Reset your RAG Evals password", html_body, text_body)
