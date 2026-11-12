/**
 * One codebase, two sites:
 * - `booking` (default build, served at /booking/): the booking service.
 * - `routes`  (`vite build --mode routes`, served at /): only the route-pack product.
 */
export type Site = 'booking' | 'routes'

export const SITE: Site = import.meta.env.VITE_SITE === 'routes' ? 'routes' : 'booking'
export const IS_ROUTE_SITE = SITE === 'routes'

/** Where to land after login/verification when no ?redirect= is given. */
export function homePath(isAdmin = false): string {
  if (IS_ROUTE_SITE) return '/'
  return isAdmin ? '/admin' : '/dashboard'
}
