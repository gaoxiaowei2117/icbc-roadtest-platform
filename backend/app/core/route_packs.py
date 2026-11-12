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
