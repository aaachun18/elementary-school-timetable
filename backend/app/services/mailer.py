"""帳號改版: the mail telling a new 教學組長 / 一般老師 their account.

Uses the standard library's smtplib (no extra dependency). Without
SMTP_HOST the mail is only written to the log -- development and tests
need no mail server. Sending never raises: a failure is logged with its
traceback and reported as False, so the caller can show the password to
the person who created the account instead."""

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from app.config import get_settings

logger = logging.getLogger(__name__)

ACCOUNT_MAIL_SUBJECT = "國小智慧排課系統 帳號通知"


@dataclass(frozen=True)
class AccountMail:
    to: str
    subject: str
    body: str


def build_account_created_mail(email: str, password: str, login_url: str) -> AccountMail:
    body = (
        f"帳號：{email}\n"
        f"密碼：{password}\n"
        "\n"
        "可以至頁面登入，若有需要可以至個人資料維護頁面修改密碼。\n"
        f"登入頁面：{login_url}\n"
    )
    return AccountMail(to=email, subject=ACCOUNT_MAIL_SUBJECT, body=body)


def deliver(mail: AccountMail) -> bool:
    """Sends the mail; True when it was sent (or logged, without SMTP)."""
    settings = get_settings()
    if not settings.smtp_host:
        # WARNING, not INFO: the backend's default logging drops INFO, and
        # this log line is then the only place the new password appears.
        logger.warning(
            "SMTP_HOST not set; account mail not sent.\nTo: %s\nSubject: %s\n\n%s",
            mail.to,
            mail.subject,
            mail.body,
        )
        return True

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = mail.to
    message["Subject"] = mail.subject
    message.set_content(mail.body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password or "")
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError):
        logger.exception("Sending the account mail to %s failed", mail.to)
        return False
    return True


def send_account_created_email(email: str, password: str) -> bool:
    mail = build_account_created_mail(email, password, get_settings().app_login_url)
    return deliver(mail)
