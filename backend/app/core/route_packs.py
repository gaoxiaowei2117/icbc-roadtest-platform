"""Route pack catalog loaded from a JSON data file.

New test centres are added by editing the data file (and restarting the API);
no code change is needed. The Google Maps links in it are only ever returned by
the purchase-gated links endpoint.
"""
import json
from functools import lru_cache
from pathlib import Path

from app.core.config import Settings, get_settings
from app.schemas.route_pack import RoutePackDef, RoutePackCatalog

DEFAULT_FILE = Path(__file__).resolve().parent.parent / "data" / "route_packs.json"


def _catalog_path() -> Path:
    configured = get_settings().route_packs_file
    return Path(configured) if configured else DEFAULT_FILE


@lru_cache
def _load(path: str) -> dict[str, RoutePackDef]:
    with open(path, encoding="utf-8") as f:
        catalog = RoutePackCatalog.model_validate(json.load(f))
    packs: dict[str, RoutePackDef] = {}
    for pack in catalog.packs:
        if pack.slug in packs:
            raise ValueError(f"路线包 slug 重复：{pack.slug}")
        packs[pack.slug] = pack
    return packs


def all_packs() -> list[RoutePackDef]:
    return list(_load(str(_catalog_path())).values())


def get_pack(slug: str) -> RoutePackDef | None:
    return _load(str(_catalog_path())).get(slug)


def price_cents(pack: RoutePackDef, settings: Settings) -> int:
    return pack.price_cents or settings.route_pack_price_cents


def currency(pack: RoutePackDef, settings: Settings) -> str:
    return (pack.currency or settings.route_pack_currency).lower()


def stripe_price_id(pack: RoutePackDef, settings: Settings) -> str:
    return pack.stripe_price_id or settings.stripe_route_pack_price_id


def checkout_enabled(pack: RoutePackDef, settings: Settings) -> bool:
    return settings.route_pack_checkout_enabled(pack.stripe_price_id)


def search_text(pack: RoutePackDef) -> str:
    """Lower-cased text that the listing's ``q`` parameter matches against."""
    parts = [pack.slug, pack.name, pack.name_zh, pack.centre, pack.city, pack.city_zh]
    return "\n".join(p for p in parts if p).casefold()


def filter_packs(
    packs: list[RoutePackDef],
    country: str | None = None,
    region: str | None = None,
    q: str | None = None,
) -> list[RoutePackDef]:
    country = (country or "").strip().upper()
    region = (region or "").strip().upper()
    needle = (q or "").strip().casefold()
    return [
        p for p in packs
        if (not country or p.country == country)
        and (not region or p.region == region)
        and (not needle or needle in search_text(p))
    ]


def facets(packs: list[RoutePackDef]) -> dict:
    countries: dict[str, dict[str, int]] = {}
    for p in packs:
        regions = countries.setdefault(p.country, {})
        regions[p.region] = regions.get(p.region, 0) + 1
    return {
        "total": len(packs),
        "countries": [
            {
                "code": code,
                "count": sum(regions.values()),
                "regions": [{"code": r, "count": n} for r, n in sorted(regions.items())],
            }
            for code, regions in sorted(countries.items())
        ],
    }
