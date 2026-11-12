import { api } from './client'
import type { Site } from '@/site'

export interface RoutePack {
  slug: string
  name: string
  name_zh: string | null
  /** ISO 3166-1 alpha-2, e.g. "CA" */
  country: string
  /** ISO 3166-2 subdivision without the country prefix, e.g. "BC" */
  region: string
  city: string
  city_zh: string | null
  /** Street address */
  centre: string
  price_cents: number
  currency: string
  route_count: number
  routes: RouteSummary[]
  checkout_enabled: boolean
  /** null when not logged in */
  purchased: boolean | null
}

export interface RouteSummary {
  title: string
  segment_count: number
  /** `from`/`to`: English street names, or the token "centre" for the test centre. */
  segments: { label: string; from: string | null; to: string | null }[]
  /** Overview image path relative to the site's base URL. */
  preview: string | null
  preview_en?: string | null
  note: string | null
  note_zh: string | null
}

export interface RouteOpen {
  /** Path on this site (/api/route-packs/go/<token>) that redirects to Google Maps; valid for `expires_in` seconds. */
  url: string
  expires_in: number
}

export interface RoutePackFilters {
  country?: string
  region?: string
  q?: string
}

export interface RoutePackFacets {
  total: number
  countries: { code: string; count: number; regions: { code: string; count: number }[] }[]
}

export async function listRoutePacks(filters: RoutePackFilters = {}): Promise<RoutePack[]> {
  const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v))
  return (await api.get('/api/route-packs', { params })).data
}

export async function getRoutePack(slug: string): Promise<RoutePack> {
  return (await api.get(`/api/route-packs/${encodeURIComponent(slug)}`)).data
}

export async function getRoutePackFacets(): Promise<RoutePackFacets> {
  return (await api.get('/api/route-packs/facets')).data
}

/**
 * Only succeeds for users who bought the pack. The server logs the click and returns a
 * short-lived redirect URL; the Google Maps link itself never reaches the page.
 */
export async function openRoute(slug: string, route: number, segment = 0): Promise<RouteOpen> {
  return (await api.post(`/api/route-packs/${encodeURIComponent(slug)}/open`, { route, segment })).data
}

/** `site` picks the Stripe return page (this site); the server maps it to a fixed URL. */
export async function createRoutePackCheckout(slug: string, site: Site): Promise<{ url: string; session_id: string }> {
  return (await api.post(`/api/route-packs/${encodeURIComponent(slug)}/checkout`, { site })).data
}
