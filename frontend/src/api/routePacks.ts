import { api } from './client'

export interface RoutePack {
  slug: string
  name: string
  name_zh: string | null
  centre: string
  price_cents: number
  currency: string
  route_count: number
  routes: { title: string; segment_count: number }[]
  checkout_enabled: boolean
  /** null when not logged in */
  purchased: boolean | null
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

export async function createRoutePackCheckout(slug: string): Promise<{ url: string; session_id: string }> {
  return (await api.post(`/api/route-packs/${encodeURIComponent(slug)}/checkout`)).data
}
