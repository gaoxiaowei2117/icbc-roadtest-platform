from unittest.mock import MagicMock, patch

from app.core import email


def test_send_email_uses_smtp(monkeypatch):
    monkeypatch.setattr(email.settings, "smtp_user", "sys@gmail.com")
    monkeypatch.setattr(email.settings, "smtp_password", "pw")
    smtp = MagicMock()
    with patch("app.core.email.smtplib.SMTP") as smtp_cls:
        smtp_cls.return_value.__enter__.return_value = smtp
        email.send_email("u@x.com", "subj", "body")
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("sys@gmail.com", "pw")
    smtp.send_message.assert_called_once()


def test_send_email_requires_config(monkeypatch):
    monkeypatch.setattr(email.settings, "smtp_user", "")
    import pytest
    with pytest.raises(ValueError):
        email.send_email("u@x.com", "s", "b")


def test_send_verification_code_calls_send_email():
    with patch("app.core.email.send_email") as send:
        email.send_verification_code("u@x.com", "123456")
    send.assert_called_once()
    args = send.call_args[0]
    assert args[0] == "u@x.com"
    assert "123456" in args[2]
