"""Short-lived redirect tokens for route-pack navigation links.

The buyer's page never receives a Google Maps link. Clicking "open navigation" asks
the API for a token (checked against the login and the purchase), and the browser
goes to /api/route-packs/go/<token>, which redirects to the link in the current data
file. A forwarded token stops working after a few minutes or once access is revoked.

What this can't do: after the redirect, the Google Maps link is visible in the
address bar / Maps app and can still be copied by hand.
"""
import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import Request
from jose import JWTError, jwt

from app.core.config import get_settings

TOKEN_TTL = timedelta(minutes=5)
_TYPE = "route_open"


def _key() -> str:
    # Derived from JWT_SECRET but different from it, so a redirect token can never be
    # taken for a login token (and vice versa), whatever decode_token checks.
    secret = get_settings().jwt_secret
    return hashlib.sha256(f"route-open:{secret}".encode()).hexdigest()


def create_token(open_id: int, user_id: int, slug: str, route_index: int, segment_index: int) -> str:
    payload = {
        "type": _TYPE,
        "oid": open_id,
        "sub": str(user_id),
        "pk": slug,
        "r": route_index,
        "s": segment_index,
        "exp": datetime.now(timezone.utc) + TOKEN_TTL,
    }
    return jwt.encode(payload, _key(), algorithm="HS256")


def decode_token(token: str) -> dict | None:
    """Claims of a valid, unexpired redirect token, else None."""
    try:
        claims = jwt.decode(token, _key(), algorithms=["HS256"])
    except JWTError:
        return None
    if claims.get("type") != _TYPE:
        return None
    try:
        return {
            "open_id": int(claims["oid"]),
            "user_id": int(claims["sub"]),
            "slug": str(claims["pk"]),
            "route_index": int(claims["r"]),
            "segment_index": int(claims["s"]),
        }
    except (KeyError, TypeError, ValueError):
        return None


def client_ip(request: Request) -> str | None:
    """Best-effort client IP for the open log: Cloudflare's header, then nginx's, then the socket."""
    for header in ("cf-connecting-ip", "x-real-ip"):
        value = request.headers.get(header)
        if value:
            return value.strip()[:64]
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host[:64] if request.client else None
