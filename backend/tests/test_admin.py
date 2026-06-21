"""admin 鉴权隔离与用户管理。"""
from app.models.booking import Booking
from app.models.secret import Secret
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


def test_admin_can_list_users(client, auth_headers, db):
    auth_headers(email="user1@gmail.com")
    admin_headers = auth_headers(email="admin@gmail.com")
    admin = db.query(User).filter_by(email="admin@gmail.com").first()
    admin.is_admin = True
    db.commit()

    response = client.get("/api/admin/users", headers=admin_headers)

    assert response.status_code == 200
    assert {user["email"] for user in response.json()} == {
        "user1@gmail.com", "admin@gmail.com"
    }
    assert all("password_hash" not in user for user in response.json())
    assert all("ciphertext" not in user for user in response.json())
    assert all(user["has_secret"] is False for user in response.json())


def test_non_admin_cannot_list_or_delete_users(client, auth_headers):
    headers = auth_headers()
    assert client.get("/api/admin/users", headers=headers).status_code == 403
    assert client.delete("/api/admin/users/1", headers=headers).status_code == 403


def test_admin_can_delete_user_and_related_data(client, auth_headers, ready_user, db):
    user_headers, _, _ = ready_user(email="delete-me@gmail.com")
    assert client.post("/api/bookings", headers=user_headers, json={}).status_code == 201
    user = db.query(User).filter_by(email="delete-me@gmail.com").first()
    user_id = user.id

    admin_headers = auth_headers(email="admin@gmail.com")
    admin = db.query(User).filter_by(email="admin@gmail.com").first()
    admin.is_admin = True
    db.commit()

    bookings = client.get("/api/admin/bookings", headers=admin_headers)
    assert bookings.status_code == 200
    assert bookings.json()[0]["user_email"] == "delete-me@gmail.com"

    response = client.delete(f"/api/admin/users/{user_id}", headers=admin_headers)

    assert response.status_code == 204
    db.expire_all()
    assert db.get(User, user_id) is None
    assert db.query(Booking).filter_by(user_id=user_id).count() == 0
    assert db.query(Secret).filter_by(user_id=user_id).count() == 0


def test_admin_cannot_delete_admin(client, auth_headers, db):
    admin_headers = auth_headers(email="admin@gmail.com")
    admin = db.query(User).filter_by(email="admin@gmail.com").first()
    admin.is_admin = True
    db.commit()

    response = client.delete(f"/api/admin/users/{admin.id}", headers=admin_headers)

    assert response.status_code == 409
    assert db.get(User, admin.id) is not None
