"""Admin stats response (see app/core/stats.py for how each number is counted)."""
from datetime import date

from pydantic import BaseModel, ConfigDict


class StatsDayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: date
    signups: int
    verified: int
    trial_users: int
    route_opens: int
    checkouts: int
    purchases: int
    revenue_cents: int


class StatsFunnelOut(BaseModel):
    signed_up: int
    verified: int
    tried_free_route: int
    started_checkout: int
    purchased: int


class StatsSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    source: str
    signups: int
    verified: int
    tried_free_route: int
    started_checkout: int
    purchased: int


class StatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    days: int
    start: date
    end: date
    timezone: str
    currency: str
    excluded_accounts: int
    daily: list[StatsDayOut]
    totals: StatsDayOut
    funnel: StatsFunnelOut
    trial_users_all_time: int
    trial_then_purchased_all_time: int
    by_source: list[StatsSourceOut]


class StatsExclusionIn(BaseModel):
    excluded: bool
