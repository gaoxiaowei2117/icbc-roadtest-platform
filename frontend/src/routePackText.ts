import type { RoutePack } from '@/api/routePacks'
import { useI18n } from '@/i18n'
import { COUNTRY_NAMES, REGION_NAMES } from '@/regions'

/** Shared display helpers for route packs (names, location, price). */
export function useRoutePackText() {
  const { tr, locale, dateLocale } = useI18n()
  const zh = () => locale.value.startsWith('zh')

  function packName(pack: RoutePack) {
    return zh() && pack.name_zh ? pack.name_zh : pack.name
  }

  function cityName(pack: RoutePack) {
    return zh() && pack.city_zh ? pack.city_zh : pack.city
  }

  function countryName(code: string) {
    const n = COUNTRY_NAMES[code]
    return n ? tr(n[0], n[1]) : code
  }

  function regionName(country: string, region: string) {
    const n = REGION_NAMES[country]?.[region]
    return n ? tr(n[0], n[1]) : region
  }

  /** "Burnaby, BC" / "本拿比 · BC" (region as code, short enough for cards). */
  function placeLine(pack: RoutePack) {
    return zh() ? `${cityName(pack)} · ${pack.region}` : `${cityName(pack)}, ${pack.region}`
  }

  function formatPrice(pack: RoutePack) {
    return new Intl.NumberFormat(dateLocale.value, {
      style: 'currency',
      currency: pack.currency.toUpperCase(),
      currencyDisplay: 'code',
    }).format(pack.price_cents / 100)
  }

  return { packName, cityName, countryName, regionName, placeLine, formatPrice }
}
