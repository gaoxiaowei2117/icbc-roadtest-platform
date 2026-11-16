/**
 * First-touch attribution: where a visitor first came from, sent with the sign-up.
 *
 * `captureFirstTouch` runs on every page load of the app and, as an inline script,
 * on the static route pages (seo/pages.ts inlines its source via toString(), so keep
 * it self-contained: no imports, no outer variables). It keeps the first visit that
 * arrived from another site or with utm_* params for 30 days; internal navigation
 * never overwrites it. The server classifies it (backend app/core/attribution.py).
 */
export function captureFirstTouch(): void {
  try {
    const KEY = 'rtg.first_touch'
    const MAX_AGE_MS = 30 * 24 * 3600 * 1000
    const q = new URLSearchParams(window.location.search)
    const utm: Record<string, string> = {}
    for (const k of ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content']) {
      const v = q.get(k)
      if (v) utm[k] = v.slice(0, 100)
    }
    let ref = ''
    try {
      ref = document.referrer && new URL(document.referrer).host !== window.location.host ? document.referrer : ''
    } catch {
      ref = ''
    }
    const external = !!ref || Object.keys(utm).length > 0
    const old = JSON.parse(localStorage.getItem(KEY) || 'null')
    const fresh = old && typeof old.ts === 'number' && Date.now() - old.ts < MAX_AGE_MS
    const oldExternal = fresh && (!!old.referrer || !!old.utm_source)
    // Keep a fresh external touch; a stored direct visit gives way to a later external one.
    if (oldExternal || (fresh && !external)) return
    localStorage.setItem(
      KEY,
      JSON.stringify({ ...utm, referrer: ref.slice(0, 300), landing: window.location.pathname.slice(0, 300), ts: Date.now() }),
    )
  } catch {
    // storage blocked: no attribution, the sign-up counts as direct
  }
}

/** The stored first touch, shaped for the register API (or undefined). */
export function firstTouch(): Record<string, string> | undefined {
  try {
    const raw = JSON.parse(localStorage.getItem('rtg.first_touch') || 'null')
    if (!raw || typeof raw !== 'object') return undefined
    const out: Record<string, string> = {}
    for (const k of ['referrer', 'landing', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content']) {
      if (typeof raw[k] === 'string' && raw[k]) out[k] = raw[k]
    }
    return out
  } catch {
    return undefined
  }
}
