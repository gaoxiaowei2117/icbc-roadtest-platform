import { api } from './client'

/** One Vancouver calendar day (see backend app/core/stats.py for each definition). */
export interface StatsDay {
  date: string
  signups: number
  /** Of that day's sign-ups, how many have verified their email by now. */
  verified: number
  /** Users whose first free-route open was that day. */
  trial_users: number
  route_opens: number
  /** Users who started a route-pack checkout that day. */
  checkouts: number
  /** Paid (Stripe) route-pack purchases; manual grants are not counted. */
  purchases: number
  revenue_cents: number
}

export interface Stats {
  days: number
  start: string
  end: string
  timezone: string
  currency: string
  /** Admins plus accounts marked as test accounts. */
  excluded_accounts: number
  daily: StatsDay[]
  totals: StatsDay
  /** Users who signed up in the range and how far each got. */
  funnel: {
    signed_up: number
    verified: number
    tried_free_route: number
    started_checkout: number
    purchased: number
  }
  trial_users_all_time: number
  trial_then_purchased_all_time: number
  /** The range's sign-ups by first-touch source ("youtube", "google", "direct", "unknown" = before tracking). */
  by_source: StatsSource[]
}

export interface StatsSource {
  source: string
  signups: number
  verified: number
  tried_free_route: number
  started_checkout: number
  purchased: number
}

export async function getStats(days: number): Promise<Stats> {
  return (await api.get('/api/admin/stats', { params: { days } })).data
}

export async function setStatsExclusion(userId: number, excluded: boolean): Promise<{ excluded: boolean }> {
  return (await api.put(`/api/admin/users/${userId}/stats-exclusion`, { excluded })).data
}
