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


def test_route_site_verification_email_has_no_booking_branding():
    with patch("app.core.email.send_email") as m:
        email.send_verification_code("u@x.com", "654321", site="routes")
    to, subject, body = m.call_args.args
    assert to == "u@x.com"
    assert "654321" in body
    assert "抢号" not in subject and "抢号" not in body
    assert "roadtestgo" in subject


def test_register_passes_site_to_verification_email(client, monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.api.auth.send_verification_code", lambda to, code, site="booking": sent.append(site)
    )
    client.post("/api/auth/register", json={"email": "a@gmail.com", "password": "secret123", "site": "routes"})
    client.post("/api/auth/register", json={"email": "b@gmail.com", "password": "secret123"})
    client.post("/api/auth/resend-code", json={"email": "a@gmail.com", "site": "routes"})
    assert sent == ["routes", "booking", "routes"]
