/**
 * Hands the address being verified from Register/Login to the verify page without
 * putting it in the URL (a URL ends up in server logs, analytics and Referer headers).
 * sessionStorage keeps it across a reload of the same tab; if storage is blocked the
 * in-memory copy still covers the normal in-app navigation, and the verify page's
 * email field stays editable as the last resort.
 */
const KEY = 'rtg.pending_email'
let memory = ''

export function setPendingEmail(email: string): void {
  memory = email
  try { sessionStorage.setItem(KEY, email) } catch { /* storage blocked */ }
}

export function getPendingEmail(): string {
  try { return sessionStorage.getItem(KEY) || memory } catch { return memory }
}

export function clearPendingEmail(): void {
  memory = ''
  try { sessionStorage.removeItem(KEY) } catch { /* storage blocked */ }
}
