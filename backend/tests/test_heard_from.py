"""Post-purchase "how did you hear about us?": stored on the user, shown to admins, counted in stats."""
from app.models.route_pack import RoutePackPurchase, RoutePackPurchaseSource, RoutePackPurchaseStatus
from app.models.user import User


def test_answer_is_saved_and_returned_by_me(client, auth_headers, db):
    headers = auth_headers(email="buyer@gmail.com")
    assert client.get("/api/users/me", headers=headers).json()["heard_from"] is None

    r = client.put("/api/users/me/heard-from", headers=headers,
                   json={"answer": "other", "detail": "  driving school flyer  "})
    assert r.status_code == 200
    assert r.json()["heard_from"] == "other"

    u = db.query(User).filter_by(email="buyer@gmail.com").one()
    db.refresh(u)
    assert (u.heard_from, u.heard_from_detail) == ("other", "driving school flyer")
    assert u.heard_from_at is not None
    assert client.get("/api/users/me", headers=headers).json()["heard_from"] == "other"


def test_blank_detail_is_stored_as_null(client, auth_headers, db):
    headers = auth_headers(email="b2@gmail.com")
    client.put("/api/users/me/heard-from", headers=headers, json={"answer": "youtube", "detail": "   "})
    u = db.query(User).filter_by(email="b2@gmail.com").one()
    db.refresh(u)
    assert (u.heard_from, u.heard_from_detail) == ("youtube", None)


def test_rejects_unknown_answer_and_long_detail(client, auth_headers):
    headers = auth_headers(email="b3@gmail.com")
    assert client.put("/api/users/me/heard-from", headers=headers, json={"answer": "tiktok"}).status_code == 422
    assert client.put("/api/users/me/heard-from", headers=headers,
                      json={"answer": "other", "detail": "x" * 201}).status_code == 422


def test_requires_login(client):
    assert client.put("/api/users/me/heard-from", json={"answer": "youtube"}).status_code == 401


def test_admin_sees_answer_and_stats_count_it(client, auth_headers, db):
    headers = auth_headers(email="admin@gmail.com")
    admin = db.query(User).filter_by(email="admin@gmail.com").one()
    admin.is_admin = True
    a = User(email="a@gmail.com", password_hash="x", heard_from="youtube", signup_source="direct")
    b = User(email="b@gmail.com", password_hash="x", heard_from="youtube")
    c = User(email="c@gmail.com", password_hash="x", heard_from="friend", heard_from_detail="coworker")
    t = User(email="t@gmail.com", password_hash="x", heard_from="friend", exclude_from_stats=True)
    db.add_all([a, b, c, t])
    db.flush()
    db.add(RoutePackPurchase(user_id=a.id, pack_slug="burnaby-4399",
                             status=RoutePackPurchaseStatus.active, source=RoutePackPurchaseSource.stripe))
    db.commit()

    rows = client.get("/api/admin/stats", params={"days": 7}, headers=headers).json()["heard_from"]
    assert [(r["answer"], r["users"], r["purchased"]) for r in rows] == [("youtube", 2, 1), ("friend", 1, 0)]

    users = {u["email"]: u for u in client.get("/api/admin/users", headers=headers).json()}
    assert (users["a@gmail.com"]["heard_from"], users["a@gmail.com"]["signup_source"]) == ("youtube", "direct")
    assert users["c@gmail.com"]["heard_from_detail"] == "coworker"
