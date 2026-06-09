"""admin 鉴权隔离。"""
from app.models.user import User


def test_non_admin_forbidden(client, auth_headers):
    assert client.get("/api/admin/bookings", headers=auth_headers()).status_code == 403


def test_admin_allowed(client, auth_headers, db):
    h = auth_headers(email="admin@gmail.com")
    user = db.query(User).filter_by(email="admin@gmail.com").first()
    user.is_admin = True
    db.commit()
    assert client.get("/api/admin/bookings", headers=h).status_code == 200


def test_admin_requires_auth(client):
    assert client.get("/api/admin/bookings").status_code == 401
