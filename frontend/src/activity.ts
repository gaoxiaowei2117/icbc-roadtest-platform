import { useI18n } from '@/i18n'

// The worker and backend store booking activity / error messages as Chinese text
// (see worker/road_adapter.py, worker/worker.py, worker/vendor/road.py,
// backend/app/api/worker.py, backend/app/crud/booking.py). Translate the known
// shapes for display; anything unrecognized is shown as-is.
// Keep these patterns in sync if those messages change.

type Tr = ReturnType<typeof useI18n>['tr']

const FIELD_LABELS: Record<string, [string, string, string, string, string]> = {
  驾照号: ['驾照号', 'Licence number', 'Numéro de permis', 'Número de licencia', '駕照號'],
  姓氏: ['姓氏', 'Last name', 'Nom de famille', 'Apellido', '姓氏'],
  'ICBC 原始邮箱': ['ICBC 原始邮箱', 'Original ICBC email', 'Courriel ICBC d’origine', 'Correo original de ICBC', 'ICBC 原始電子郵件'],
  考试类型: ['考试类型', 'Exam class', 'Classe d’examen', 'Clase de examen', '考試類型'],
  考点: ['考点', 'Locations', 'Centres', 'Centros', '考點'],
  开始日期: ['开始日期', 'Start date', 'Date de début', 'Fecha de inicio', '開始日期'],
  结束日期: ['结束日期', 'End date', 'Date de fin', 'Fecha de fin', '結束日期'],
}

const FIXED: Record<string, [string, string, string, string, string]> = {
  任务已取消: ['任务已取消', 'Booking cancelled', 'Réservation annulée', 'Reserva cancelada', '任務已取消'],
  未知失败: ['未知失败', 'Unknown failure', 'Échec inconnu', 'Error desconocido', '未知失敗'],
  '用户未配置 ICBC keyword': [
    '用户未配置 ICBC keyword', 'ICBC keyword is not configured',
    'Le keyword ICBC n’est pas configuré', 'El keyword de ICBC no está configurado', '使用者未設定 ICBC keyword',
  ],
  'ICBC 登录身份与当前驾照配置不一致，拒绝修改邮箱': [
    'ICBC 登录身份与当前驾照配置不一致，拒绝修改邮箱',
    'ICBC login identity does not match the configured licence; email change refused',
    'L’identité de connexion ICBC ne correspond pas au permis configuré; modification du courriel refusée',
    'La identidad de inicio de sesión de ICBC no coincide con la licencia configurada; cambio de correo rechazado',
    'ICBC 登入身分與目前駕照設定不一致，拒絕修改電子郵件',
  ],
  '未配置 ICBC 原始邮箱，拒绝修改邮箱': [
    '未配置 ICBC 原始邮箱，拒绝修改邮箱',
    'Original ICBC email is not configured; email change refused',
    'Le courriel ICBC d’origine n’est pas configuré; modification du courriel refusée',
    'El correo original de ICBC no está configurado; cambio de correo rechazado',
    '未設定 ICBC 原始電子郵件，拒絕修改電子郵件',
  ],
  'ICBC 登录响应缺少邮箱，拒绝修改邮箱': [
    'ICBC 登录响应缺少邮箱，拒绝修改邮箱',
    'ICBC login response has no email; email change refused',
    'La réponse de connexion ICBC ne contient pas de courriel; modification du courriel refusée',
    'La respuesta de inicio de sesión de ICBC no incluye correo; cambio de correo rechazado',
    'ICBC 登入回應缺少電子郵件，拒絕修改電子郵件',
  ],
  'ICBC 当前邮箱与配置的原始邮箱不一致，已拒绝临时替换；任务结束时将按当前驾照配置尝试恢复': [
    'ICBC 当前邮箱与配置的原始邮箱不一致，已拒绝临时替换；任务结束时将按当前驾照配置尝试恢复',
    'Current ICBC email differs from the configured original email; temporary replacement refused. It will be restored from the current licence settings when the booking ends',
    'Le courriel ICBC actuel diffère du courriel d’origine configuré; remplacement temporaire refusé. Il sera restauré à la fin de la réservation',
    'El correo actual de ICBC no coincide con el original configurado; reemplazo temporal rechazado. Se restaurará al finalizar la reserva',
    'ICBC 目前電子郵件與設定的原始電子郵件不一致，已拒絕臨時替換；任務結束時將依目前駕照設定嘗試恢復',
  ],
  '更新 ICBC 验证邮箱失败': [
    '更新 ICBC 验证邮箱失败', 'Failed to update the ICBC verification email',
    'Échec de la mise à jour du courriel de vérification ICBC',
    'Error al actualizar el correo de verificación de ICBC', '更新 ICBC 驗證電子郵件失敗',
  ],
}

function pick(tr: Tr, t: [string, string, string, string, string]) {
  return tr(t[0], t[1], t[2], t[3], t[4])
}

export function translateActivity(message: string | null | undefined, tr: Tr): string {
  if (!message) return ''
  const text = message.trim()

  const fixed = FIXED[text]
  if (fixed) return pick(tr, fixed)

  let m = text.match(/^考点 (\S+) 查询结果 (\S+)$/)
  if (m) {
    const [, pos, status] = m
    return tr(
      `考点 ${pos} 查询结果 ${status}`, `Location ${pos}: result ${status}`,
      `Centre ${pos} : résultat ${status}`, `Centro ${pos}: resultado ${status}`, `考點 ${pos} 查詢結果 ${status}`,
    )
  }

  m = text.match(/^到达时限（(\d+)s）仍未抢到号，自动重排继续抢$/)
  if (m) {
    const s = m[1]
    return tr(
      text, `No slot found within the time limit (${s}s); requeued automatically to keep searching`,
      `Aucune place trouvée dans le délai (${s} s); remise en file automatiquement`,
      `No se encontró cita dentro del límite (${s} s); reencolada automáticamente`,
      `到達時限（${s}s）仍未搶到號，自動重排繼續搶`,
    )
  }

  m = text.match(/^worker 超时（>(\d+) 分钟）未完成，自动重置重排$/)
  if (m) {
    const n = m[1]
    return tr(
      text, `Worker timed out (> ${n} min); reset and requeued automatically`,
      `Délai du worker dépassé (> ${n} min); réinitialisée et remise en file`,
      `Tiempo de espera del worker agotado (> ${n} min); reiniciada y reencolada`,
      `worker 逾時（>${n} 分鐘）未完成，自動重設重排`,
    )
  }

  m = text.match(/^档案不完整，缺少：(.+)$/)
  if (m) {
    const labels = m[1].split('、').map((f) => (FIELD_LABELS[f] ? pick(tr, FIELD_LABELS[f]) : f))
    const list = tr(labels.join('、'), labels.join(', '), labels.join(', '), labels.join(', '), labels.join('、'))
    return tr(
      text, `Profile incomplete; missing: ${list}`, `Profil incomplet; champs manquants : ${list}`,
      `Perfil incompleto; falta: ${list}`, `資料不完整，缺少：${list}`,
    )
  }

  m = text.match(/^凭据解密失败：([\s\S]*)$/)
  if (m) {
    const e = m[1]
    return tr(
      text, `Failed to decrypt credentials: ${e}`, `Échec du déchiffrement des identifiants : ${e}`,
      `Error al descifrar las credenciales: ${e}`, `憑證解密失敗：${e}`,
    )
  }

  m = text.match(/^worker 异常：([\s\S]*)$/)
  if (m) {
    const e = m[1]
    return tr(text, `Worker error: ${e}`, `Erreur du worker : ${e}`, `Error del worker: ${e}`, `worker 異常：${e}`)
  }

  return message
}
