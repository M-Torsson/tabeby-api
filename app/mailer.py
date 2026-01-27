# Author: Muthana
# © 2026 Muthana. All rights reserved.
# Unauthorized copying or distribution is prohibited.


import os
import smtplib
from email.message import EmailMessage
from typing import Optional

import json
import requests

EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Tabeby").strip()

RESEND_API_KEY = os.getenv("RESEND_API_KEY")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASS") or os.getenv("SMTP_PASSWORD")
SMTP_USE_TLS = os.getenv("SMTP_TLS", "true").lower() in ("1", "true", "yes")
SMTP_USE_SSL = os.getenv("SMTP_SSL", "false").lower() in ("1", "true", "yes")


def _format_from_address() -> Optional[str]:
    sender = EMAIL_FROM or SMTP_USER
    if not sender:
        return None
    name = EMAIL_FROM_NAME or ""
    return f"{name} <{sender}>" if name else sender


def _send_via_resend(to_email: str, subject: str, html_body: str, text_body: Optional[str]) -> bool:
    if not RESEND_API_KEY or not EMAIL_FROM:
        return False
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "from": _format_from_address(),
                "to": [to_email],
                "subject": subject,
                "html": html_body,
                "text": text_body or "",
            }),
            timeout=15,
        )
        if 200 <= resp.status_code < 300:
            return True
        return False
    except Exception as e:
        return False


def _send_via_smtp(to_email: str, subject: str, html_body: str, text_body: Optional[str]) -> bool:
    from_addr = _format_from_address()
    if not SMTP_HOST or not from_addr:
        return False

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_email
    msg["Subject"] = subject
    if text_body:
        msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    try:
        if SMTP_USE_SSL:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
                if SMTP_USER and SMTP_PASSWORD:
                    server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.ehlo()
                if SMTP_USE_TLS:
                    server.starttls()
                if SMTP_USER and SMTP_PASSWORD:
                    server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        return True
    except Exception as e:
        return False


def _send_email(to_email: str, subject: str, html_body: str, text_body: Optional[str] = None) -> bool:
    if _send_via_resend(to_email, subject, html_body, text_body):
        return True
    if _send_via_smtp(to_email, subject, html_body, text_body):
        return True
    return False


def send_password_reset(to_email: str, reset_link: str) -> bool:
    subject = "Reset your password"
    text_body = f"Use the following link to reset your password: {reset_link}"
    html_body = f"""
    <p>Hello,</p>
    <p>Click the link below to reset your password:</p>
    <p><a href="{reset_link}">Reset Password</a></p>
    <p>If you did not request this, you can ignore this email.</p>
    """
    return _send_email(to_email, subject, html_body, text_body)
