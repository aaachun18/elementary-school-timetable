"""帳號改版: the initial password generator and the account mail, on their
own (no database, no FastAPI)."""

import smtplib
from typing import Any

import pytest

from app.config import get_settings
from app.schemas.user import validate_password
from app.services import mailer
from app.services.mailer import build_account_created_mail
from app.services.password_generator import generate_initial_password


def test_initial_password_is_8_letters_and_digits() -> None:
    for _ in range(200):
        password = generate_initial_password()
        assert len(password) == 8
        assert password.isalnum()
        assert any(char.isdigit() for char in password)
        assert any(char.isalpha() for char in password)
        assert not set(password) & set("0O1lI")
        assert validate_password(password) == password


def test_initial_passwords_differ() -> None:
    assert len({generate_initial_password() for _ in range(50)}) > 45


def test_mail_body() -> None:
    mail = build_account_created_mail("t1@example.com", "Ab3dEf7h", "http://host/login")

    assert mail.to == "t1@example.com"
    assert mail.body.splitlines()[:2] == ["帳號：t1@example.com", "密碼：Ab3dEf7h"]
    assert "可以至頁面登入，若有需要可以至個人資料維護頁面修改密碼。" in mail.body
    assert "http://host/login" in mail.body


@pytest.fixture
def real_deliver(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Undoes conftest's autouse fake so the real deliver() runs."""
    monkeypatch.undo()
    yield mailer.deliver
    get_settings.cache_clear()


def test_without_smtp_host_mail_is_logged(
    real_deliver: Any, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("SMTP_HOST", "")
    get_settings.cache_clear()
    caplog.set_level("INFO", logger="app.services.mailer")

    sent = real_deliver(build_account_created_mail("t1@example.com", "Ab3dEf7h", "x"))

    assert sent is True
    assert "密碼：Ab3dEf7h" in caplog.text


def test_without_smtp_host_mail_shows_at_default_log_level(
    real_deliver: Any, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Regression: the mail was logged at INFO, which the backend's default
    # logging (WARNING) drops -- the new account's password was then shown
    # nowhere. It must reach the log at WARNING.
    monkeypatch.setenv("SMTP_HOST", "")
    get_settings.cache_clear()
    caplog.set_level("WARNING")

    real_deliver(build_account_created_mail("t1@example.com", "Ab3dEf7h", "x"))

    assert any(
        record.levelname == "WARNING" and "Ab3dEf7h" in record.getMessage()
        for record in caplog.records
    )


def test_smtp_failure_returns_false(
    real_deliver: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.invalid")
    get_settings.cache_clear()

    def refuse(*args: Any, **kwargs: Any) -> None:
        raise smtplib.SMTPConnectError(421, "unavailable")

    monkeypatch.setattr(smtplib, "SMTP", refuse)

    assert real_deliver(build_account_created_mail("t1@example.com", "Ab3dEf7h", "x")) is False
