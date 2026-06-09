"""auth flow：注册 / 登录 / 刷新 / JWT 鉴权。"""


def test_register_returns_tokens(client):
    r = client.post("/api/auth/register", json={"email": "a@gmail.com", "password": "secret123"})
    assert r.status_code == 201
    body = r.json()
    assert body["access_token"] and body["refresh_token"]


def test_register_duplicate_conflict(client):
    client.post("/api/auth/register", json={"email": "a@gmail.com", "password": "secret123"})
    r = client.post("/api/auth/register", json={"email": "a@gmail.com", "password": "secret123"})
    assert r.status_code == 409


def test_login_wrong_password_unauthorized(client):
    client.post("/api/auth/register", json={"email": "a@gmail.com", "password": "secret123"})
    r = client.post("/api/auth/login", json={"email": "a@gmail.com", "password": "WRONG"})
    assert r.status_code == 401


def test_login_success(client):
    client.post("/api/auth/register", json={"email": "a@gmail.com", "password": "secret123"})
    r = client.post("/api/auth/login", json={"email": "a@gmail.com", "password": "secret123"})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_refresh_issues_new_access_token(client):
    client.post("/api/auth/register", json={"email": "a@gmail.com", "password": "secret123"})
    rt = client.post("/api/auth/login",
                     json={"email": "a@gmail.com", "password": "secret123"}).json()["refresh_token"]
    r = client.post("/api/auth/refresh", json={"refresh_token": rt})
    assert r.status_code == 200 and r.json()["access_token"]


def test_refresh_rejects_access_token(client):
    """access token 不能当 refresh 用（type 校验）。"""
    client.post("/api/auth/register", json={"email": "a@gmail.com", "password": "secret123"})
    at = client.post("/api/auth/login",
                     json={"email": "a@gmail.com", "password": "secret123"}).json()["access_token"]
    r = client.post("/api/auth/refresh", json={"refresh_token": at})
    assert r.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/users/me").status_code == 401


def test_me_with_token(client, auth_headers):
    r = client.get("/api/users/me", headers=auth_headers())
    assert r.status_code == 200
    assert r.json()["email"] == "user@gmail.com"
