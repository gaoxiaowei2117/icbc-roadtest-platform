from unittest.mock import MagicMock, patch

from app.core import email


def test_send_email_uses_smtp(monkeypatch):
    monkeypatch.setattr(email.settings, "smtp_user", "sys@gmail.com")
    monkeypatch.setattr(email.settings, "smtp_password", "pw")
    smtp = MagicMock()
    with patch("app.core.email.smtplib.SMTP") as smtp_cls:
        smtp_cls.return_value.__enter__.return_value = smtp
        email.send_email("u@x.com", "subj", "body")
    assert smtp_cls.call_args.kwargs["timeout"] == email.SMTP_TIMEOUT_SECONDS
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


def test_register_succeeds_and_logs_when_email_fails(client, monkeypatch, caplog):
    def boom(*a, **k):
        raise OSError("smtp down")

    monkeypatch.setattr("app.api.auth.send_verification_code", boom)
    with caplog.at_level("ERROR", logger="icbc.auth"):
        r = client.post("/api/auth/register", json={"email": "c@gmail.com", "password": "secret123"})
        resend = client.post("/api/auth/resend-code", json={"email": "c@gmail.com"})
    assert r.status_code == 201
    assert resend.status_code == 200
    failures = [rec for rec in caplog.records if "验证码邮件发送失败" in rec.getMessage()]
    assert len(failures) == 2
    assert "c@gmail.com" not in caplog.text


def _smtp_factory(fail_hosts, calls, login_error=None):
    """Fake smtplib.SMTP: connecting to a host in fail_hosts raises; records every host tried."""
    def make(host, port, timeout):
        calls.append(host)
        if host in fail_hosts:
            raise TimeoutError("timed out")
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.__exit__.return_value = False
        if login_error:
            conn.login.side_effect = login_error
        return conn
    return make


def _configure(monkeypatch, host="smtp.gmail.com", fallbacks="1.1.1.1, 2.2.2.2"):
    monkeypatch.setattr(email.settings, "smtp_user", "sys@gmail.com")
    monkeypatch.setattr(email.settings, "smtp_password", "pw")
    monkeypatch.setattr(email.settings, "smtp_host", host)
    monkeypatch.setattr(email.settings, "smtp_fallback_hosts", fallbacks)


def test_smtp_hosts_dedupes_and_skips_blanks(monkeypatch):
    _configure(monkeypatch, host="1.1.1.1", fallbacks="1.1.1.1, ,2.2.2.2,")
    assert email.smtp_hosts() == ["1.1.1.1", "2.2.2.2"]


def test_falls_back_to_next_host_when_unreachable(monkeypatch):
    _configure(monkeypatch)
    calls = []
    with patch("app.core.email.smtplib.SMTP", side_effect=_smtp_factory({"smtp.gmail.com"}, calls)):
        email.send_email("u@x.com", "s", "b")
    assert calls == ["smtp.gmail.com", "1.1.1.1"]


def test_raises_last_error_when_every_host_fails(monkeypatch):
    _configure(monkeypatch)
    calls = []
    import pytest
    with patch("app.core.email.smtplib.SMTP",
               side_effect=_smtp_factory({"smtp.gmail.com", "1.1.1.1", "2.2.2.2"}, calls)):
        with pytest.raises(TimeoutError):
            email.send_email("u@x.com", "s", "b")
    assert calls == ["smtp.gmail.com", "1.1.1.1", "2.2.2.2"]


def test_bad_password_is_not_retried_on_other_hosts(monkeypatch):
    import smtplib
    import pytest
    _configure(monkeypatch)
    calls = []
    err = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    with patch("app.core.email.smtplib.SMTP", side_effect=_smtp_factory(set(), calls, login_error=err)):
        with pytest.raises(smtplib.SMTPAuthenticationError):
            email.send_email("u@x.com", "s", "b")
    assert calls == ["smtp.gmail.com"]


def test_no_resend_when_only_the_goodbye_fails(monkeypatch):
    import smtplib
    _configure(monkeypatch)
    calls = []
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.__exit__.side_effect = smtplib.SMTPServerDisconnected("closed")
    def make(host, port, timeout):
        calls.append(host)
        return conn
    with patch("app.core.email.smtplib.SMTP", side_effect=make):
        email.send_email("u@x.com", "s", "b")
    assert calls == ["smtp.gmail.com"]
    conn.send_message.assert_called_once()
