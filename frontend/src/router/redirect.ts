import type { LocationQuery } from 'vue-router'

/**
 * In-app path to return to after login/registration (e.g. `/routes`).
 * Only same-app absolute paths are accepted, so `?redirect=` can't send users off-site.
 */
export function safeRedirect(query: LocationQuery): string | null {
  const value = query.redirect
  if (typeof value !== 'string') return null
  if (!value.startsWith('/') || value.startsWith('//') || value.includes('\\')) return null
  return value
}

/** Query object that carries the redirect on to the next auth page. */
export function redirectQuery(query: LocationQuery): Record<string, string> {
  const redirect = safeRedirect(query)
  return redirect ? { redirect } : {}
}
