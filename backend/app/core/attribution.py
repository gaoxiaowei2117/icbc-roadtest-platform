"""Where a sign-up came from (first touch), recorded once at registration.

The browser keeps the first external visit (referrer host, landing path, utm_*)
for 30 days and sends it with the sign-up; see frontend/src/attribution.ts and the
same snippet in the static pages (frontend/seo/pages.ts). Everything here is
client-supplied, so it is trimmed and only used for counting in the admin stats.
"""
import re

from pydantic import BaseModel, Field

# Referrer host (suffix match) → source name. Order matters: first match wins.
_HOSTS: list[tuple[str, str]] = [
    ("youtube.com", "youtube"), ("youtu.be", "youtube"),
    ("google.", "google"),  # google.com, google.ca, … (matched as a label prefix below)
    ("bing.com", "bing"),
    ("chatgpt.com", "chatgpt"), ("openai.com", "chatgpt"),
    ("perplexity.ai", "perplexity"),
    ("claude.ai", "claude"),
    ("copilot.microsoft.com", "copilot"),
    ("duckduckgo.com", "duckduckgo"),
    ("baidu.com", "baidu"),
    ("xiaohongshu.com", "xiaohongshu"), ("xhslink.com", "xiaohongshu"),
    ("facebook.com", "facebook"), ("fb.com", "facebook"),
    ("instagram.com", "instagram"),
    ("reddit.com", "reddit"),
    ("weixin.qq.com", "wechat"), ("wechat.com", "wechat"),
]
_NAME = re.compile(r"[^a-z0-9._-]")


class AttributionIn(BaseModel):
    """First touch as the browser saw it; every field optional and length-capped."""
    referrer: str | None = Field(default=None, max_length=300)
    landing: str | None = Field(default=None, max_length=300)
    utm_source: str | None = Field(default=None, max_length=100)
    utm_medium: str | None = Field(default=None, max_length=100)
    utm_campaign: str | None = Field(default=None, max_length=100)
    utm_content: str | None = Field(default=None, max_length=100)


def _host(referrer: str) -> str:
    m = re.match(r"^[a-z][a-z0-9+.-]*://([^/?#:]+)", referrer.strip().lower())
    return m.group(1) if m else ""


def _source_for_host(host: str) -> str:
    for suffix, name in _HOSTS:
        if suffix.endswith("."):
            # "google." → any label sequence containing "google." (www.google.ca, google.com).
            if host.startswith(suffix) or f".{suffix}" in host:
                return name
        elif host == suffix or host.endswith(f".{suffix}"):
            return name
    return host.removeprefix("www.")[:40] or "direct"


def classify(attr: AttributionIn | None, own_host: str = "roadtestgo.com") -> tuple[str, str | None, str | None]:
    """→ (source, detail, landing). utm_source wins over the referrer; no data → "direct"."""
    if attr is None:
        return "direct", None, None
    landing = (attr.landing or "").strip()[:200] or None
    if attr.utm_source:
        source = _NAME.sub("", attr.utm_source.strip().lower())[:40] or "direct"
        detail = "/".join(x.strip() for x in (attr.utm_medium, attr.utm_campaign, attr.utm_content) if x and x.strip())
        return source, detail[:200] or None, landing
    host = _host(attr.referrer or "")
    if not host or host == own_host or host.endswith(f".{own_host}"):
        return "direct", None, landing
    return _source_for_host(host), host[:200], landing
