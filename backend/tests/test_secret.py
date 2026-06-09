"""ICBC 凭据：SealedBox 加密落库 + 后端无明文（F4 回归 + S1 安全属性）。"""
from app.models.secret import Secret


def test_put_secret_succeeds(client, auth_headers):
    """F4 回归：保存凭据不再 500。"""
    r = client.put("/api/users/me/secret", headers=auth_headers(),
                   json={"icbc_username": "myuser", "icbc_password": "mypass"})
    assert r.status_code == 200
    assert r.json()["has_secret"] is True


def test_secret_stored_as_ciphertext(client, auth_headers, db):
    """S1：DB 里存的是密文，明文不出现在 ciphertext 中。"""
    client.put("/api/users/me/secret", headers=auth_headers(),
               json={"icbc_username": "plainuser", "icbc_password": "plainpass"})
    secret = db.query(Secret).first()
    ct = bytes(secret.ciphertext)
    assert b"plainuser" not in ct
    assert b"plainpass" not in ct
    assert len(ct) > 0


def test_secret_roundtrip_via_test_private_key(client, auth_headers, db, decrypt_secret):
    """用测试私钥能解回原文 —— 验证加密链路正确。"""
    import base64
    client.put("/api/users/me/secret", headers=auth_headers(),
               json={"icbc_username": "u-rt", "icbc_password": "p-rt"})
    secret = db.query(Secret).first()
    u, p = decrypt_secret(base64.b64encode(bytes(secret.ciphertext)).decode())
    assert (u, p) == ("u-rt", "p-rt")


def test_secret_status_reflects_state(client, auth_headers):
    h = auth_headers()
    assert client.get("/api/users/me/secret", headers=h).json()["has_secret"] is False
    client.put("/api/users/me/secret", headers=h,
               json={"icbc_username": "u", "icbc_password": "p"})
    assert client.get("/api/users/me/secret", headers=h).json()["has_secret"] is True


def test_secret_delete(client, auth_headers):
    h = auth_headers()
    client.put("/api/users/me/secret", headers=h, json={"icbc_username": "u", "icbc_password": "p"})
    assert client.delete("/api/users/me/secret", headers=h).status_code == 204
    assert client.get("/api/users/me/secret", headers=h).json()["has_secret"] is False
