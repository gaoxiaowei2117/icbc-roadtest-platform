"""Route pack schemas: the data-file catalog and the API responses."""
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
# ISO 3166-1 alpha-2 country, and the ISO 3166-2 subdivision part after "CA-" / "US-".
_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
_REGION_RE = re.compile(r"^[A-Z0-9]{1,3}$")


# ---- Catalog (app/data/route_packs.json) -------------------------------------

class RouteSegmentDef(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    label: str = Field(min_length=1, max_length=100)
    # Start / end of the segment, shown publicly: English street names, or the
    # token "centre" for the test centre (the UI translates it).
    from_: str | None = Field(default=None, alias="from", max_length=100)
    to: str | None = Field(default=None, max_length=100)
    url: str = Field(min_length=1)

    @field_validator("url")
    @classmethod
    def _check_url(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("路线链接必须是 https:// 开头的 Google Maps 链接")
        return v


class RouteDef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=100)
    # Overview image, relative to the frontend's public dir (served by both sites),
    # e.g. "route-previews/burnaby-4399/route1.jpg". Shown before purchase.
    preview: str | None = None
    # Same image with English labels, shown when the UI is not Chinese (falls back to `preview`).
    preview_en: str | None = None
    # Optional public note shown under the route (English / Chinese).
    note: str | None = Field(default=None, max_length=500)
    note_zh: str | None = Field(default=None, max_length=500)
    # Google Maps app links carry at most 9 waypoints, so long routes are split.
    segments: list[RouteSegmentDef] = Field(min_length=1, max_length=3)

    @field_validator("preview", "preview_en")
    @classmethod
    def _check_preview(cls, v: str | None) -> str | None:
        if v is not None and (v.startswith("/") or ":" in v or ".." in v):
            raise ValueError("preview 必须是前端 public 目录下的相对路径")
        return v


class RoutePackDef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str
    name: str = Field(min_length=1)
    name_zh: str | None = None
    # Location, used to browse by country → region → centre and for search.
    country: str
    region: str
    city: str = Field(min_length=1, max_length=100)
    city_zh: str | None = Field(default=None, max_length=100)
    # Street address of the test centre.
    centre: str = Field(min_length=1)
    # Optional per-pack overrides of ROUTE_PACK_PRICE_CENTS / ROUTE_PACK_CURRENCY /
    # STRIPE_ROUTE_PACK_PRICE_ID. Keep price_cents equal to the Stripe Price amount.
    price_cents: int | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    stripe_price_id: str | None = None
    routes: list[RouteDef] = Field(min_length=1)

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError("slug 只能包含小写字母、数字和连字符")
        return v

    @field_validator("country")
    @classmethod
    def _check_country(cls, v: str) -> str:
        if not _COUNTRY_RE.match(v):
            raise ValueError("country 必须是 ISO 3166-1 两位大写字母代码，例如 CA")
        return v

    @field_validator("region")
    @classmethod
    def _check_region(cls, v: str) -> str:
        if not _REGION_RE.match(v):
            raise ValueError("region 必须是 ISO 3166-2 地区代码（不含国家前缀），例如 BC")
        return v


class RoutePackCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    packs: list[RoutePackDef]


# ---- API responses ------------------------------------------------------------

class RouteSegmentSummaryOut(BaseModel):
    """Public segment info: where it goes, never the link."""
    model_config = ConfigDict(populate_by_name=True)
    label: str
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None


class RouteSummaryOut(BaseModel):
    title: str
    segment_count: int
    segments: list[RouteSegmentSummaryOut]
    preview: str | None = None
    preview_en: str | None = None
    note: str | None = None
    note_zh: str | None = None


class RoutePackOut(BaseModel):
    """Public pack info. Never contains the Google Maps links."""
    slug: str
    name: str
    name_zh: str | None
    country: str
    region: str
    city: str
    city_zh: str | None
    centre: str
    price_cents: int
    currency: str
    route_count: int
    routes: list[RouteSummaryOut]
    checkout_enabled: bool
    # None for anonymous requests.
    purchased: bool | None = None


class RegionFacetOut(BaseModel):
    code: str
    count: int


class CountryFacetOut(BaseModel):
    code: str
    count: int
    regions: list[RegionFacetOut]


class RoutePackFacetsOut(BaseModel):
    """Countries/regions that have at least one pack, for the browse dropdowns."""
    total: int
    countries: list[CountryFacetOut]


class RouteSegmentOut(BaseModel):
    label: str
    url: str


class RouteLinksOut(BaseModel):
    title: str
    segments: list[RouteSegmentOut]


class RoutePackLinksOut(BaseModel):
    slug: str
    routes: list[RouteLinksOut]


class RoutePackCheckoutIn(BaseModel):
    # Which site the purchase started from; decides the Stripe return URL.
    # Only these two fixed values are accepted, never a client-supplied URL.
    site: Literal["booking", "routes"] = "booking"


class RoutePackGrantIn(BaseModel):
    email: EmailStr


class RoutePackPurchaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    user_email: str | None = None
    pack_slug: str
    status: str
    source: str
    payment_id: int | None
    granted_by: int | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime | None
