"""auth flow：注册发码 / 邮箱验证 / 登录需已验证 / 刷新。"""
from app.models.user import User


def _register(client, email="a@gmail.com", password="secret123"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def _code(db, email):
    return db.query(User).filter_by(email=email).first().verify_code


def test_register_sends_code_no_token(client, db):
    r = _register(client)
    assert r.status_code == 201
    assert "access_token" not in r.json()
    u = db.query(User).filter_by(email="a@gmail.com").first()
    assert u.email_verified is False
    assert u.verify_code and len(u.verify_code) == 6


def test_register_duplicate_conflict(client):
    _register(client)
    assert _register(client).status_code == 409


def test_login_blocked_before_verify(client):
    _register(client)
    r = client.post("/api/auth/login", json={"email": "a@gmail.com", "password": "secret123"})
    assert r.status_code == 403


def test_verify_email_then_login(client, db):
    _register(client)
    code = _code(db, "a@gmail.com")
    r = client.post("/api/auth/verify-email", json={"email": "a@gmail.com", "code": code})
    assert r.status_code == 200
    assert r.json()["access_token"]
    db.expire_all()
    assert db.query(User).filter_by(email="a@gmail.com").first().email_verified is True
    assert client.post("/api/auth/login",
                       json={"email": "a@gmail.com", "password": "secret123"}).status_code == 200


def test_verify_wrong_code(client):
    _register(client)
    r = client.post("/api/auth/verify-email", json={"email": "a@gmail.com", "code": "000000"})
    assert r.status_code == 400


def test_verify_already_verified_rejected(client, db):
    _register(client)
    code = _code(db, "a@gmail.com")
    client.post("/api/auth/verify-email", json={"email": "a@gmail.com", "code": code})
    r = client.post("/api/auth/verify-email", json={"email": "a@gmail.com", "code": code})
    assert r.status_code == 400


def test_resend_code(client, db):
    _register(client)
    r = client.post("/api/auth/resend-code", json={"email": "a@gmail.com"})
    assert r.status_code == 200
    db.expire_all()
    assert _code(db, "a@gmail.com") is not None
    r2 = client.post("/api/auth/resend-code", json={"email": "nobody@gmail.com"})
    assert r2.status_code == 200


def test_me_requires_auth(client):
    assert client.get("/api/users/me").status_code == 401
