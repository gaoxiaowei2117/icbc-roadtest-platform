"""Sign-up source: classified from the browser's first touch, counted in the admin stats."""
from datetime import datetime, timezone

import pytest

from app.core.attribution import AttributionIn, classify
from app.models.user import User


@pytest.mark.parametrize("referrer,source,detail", [
    ("https://www.youtube.com/", "youtube", "www.youtube.com"),
    ("https://m.youtube.com/watch?v=x", "youtube", "m.youtube.com"),
    ("https://www.google.ca/", "google", "www.google.ca"),
    ("https://google.com/search?q=x", "google", "google.com"),
    ("https://chatgpt.com/", "chatgpt", "chatgpt.com"),
    ("https://www.perplexity.ai/search", "perplexity", "www.perplexity.ai"),
    ("https://www.xiaohongshu.com/explore/1", "xiaohongshu", "www.xiaohongshu.com"),
    ("https://forum.example.org/t/1", "forum.example.org", "forum.example.org"),
    ("https://roadtestgo.com/zh/", "direct", None),       # our own pages are not a source
    ("https://www.roadtestgo.com/", "direct", None),
    ("not a url", "direct", None),
    ("", "direct", None),
])
def test_classify_by_referrer(referrer, source, detail):
    assert classify(AttributionIn(referrer=referrer, landing="/en/")) == (source, detail, "/en/")


def test_utm_source_wins_and_is_sanitised():
    attr = AttributionIn(referrer="https://www.google.com/", utm_source="YouTube<script>",
                         utm_medium="video", utm_content="aB0cEr2vDvs")
    assert classify(attr) == ("youtubescript", "video/aB0cEr2vDvs", None)


def test_no_attribution_is_direct():
    assert classify(None) == ("direct", None, None)


def test_register_stores_source(client, db):
    r = client.post("/api/auth/register", json={
        "email": "yt@gmail.com", "password": "secret123", "site": "routes",
        "attribution": {"referrer": "https://www.youtube.com/", "landing": "/zh/richmond-5300/route-1/"},
    })
    assert r.status_code == 201
    u = db.query(User).filter_by(email="yt@gmail.com").one()
    assert (u.signup_source, u.signup_detail, u.signup_landing) == (
        "youtube", "www.youtube.com", "/zh/richmond-5300/route-1/",
    )


def test_register_without_attribution_is_direct(client, db):
    client.post("/api/auth/register", json={"email": "d@gmail.com", "password": "secret123"})
    assert db.query(User).filter_by(email="d@gmail.com").one().signup_source == "direct"


def test_register_rejects_oversized_attribution(client):
    r = client.post("/api/auth/register", json={
        "email": "big@gmail.com", "password": "secret123", "attribution": {"landing": "/" + "x" * 400},
    })
    assert r.status_code == 422


def test_stats_split_signups_by_source(client, auth_headers, db):
    headers = auth_headers(email="admin@gmail.com")
    admin = db.query(User).filter_by(email="admin@gmail.com").one()
    admin.is_admin = True
    now = datetime.now(timezone.utc)
    for email, src, verified in [("a@gmail.com", "youtube", True), ("b@gmail.com", "youtube", False),
                                 ("c@gmail.com", "google", True), ("d@gmail.com", None, True)]:
        db.add(User(email=email, password_hash="x", email_verified=verified, signup_source=src, created_at=now))
    db.commit()
    rows = client.get("/api/admin/stats", params={"days": 7}, headers=headers).json()["by_source"]
    assert [(r["source"], r["signups"], r["verified"]) for r in rows] == [
        ("youtube", 2, 1), ("google", 1, 1), ("unknown", 1, 1),
    ]
