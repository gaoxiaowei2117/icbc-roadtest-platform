import { api } from './client'
import type { Site } from '@/site'

export interface RoutePack {
  slug: string
  name: string
  name_zh: string | null
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
  note: string | null
  note_zh: string | null
}

export interface RoutePackLinks {
  slug: string
  routes: { title: string; segments: { label: string; url: string }[] }[]
}

export async function listRoutePacks(): Promise<RoutePack[]> {
  return (await api.get('/api/route-packs')).data
}

/** Only succeeds for users who bought the pack; the links are never part of the page itself. */
export async function getRoutePackLinks(slug: string): Promise<RoutePackLinks> {
  return (await api.get(`/api/route-packs/${encodeURIComponent(slug)}/links`)).data
}

/** `site` picks the Stripe return page (this site); the server maps it to a fixed URL. */
export async function createRoutePackCheckout(slug: string, site: Site): Promise<{ url: string; session_id: string }> {
  return (await api.post(`/api/route-packs/${encodeURIComponent(slug)}/checkout`, { site })).data
}
