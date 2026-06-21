import { computed, ref, watch } from 'vue'

export type Locale = 'zh' | 'zh-Hant' | 'en' | 'fr' | 'es'

const supported: Locale[] = ['zh', 'zh-Hant', 'en', 'fr', 'es']
const saved = localStorage.getItem('icbc.locale') as Locale | null
const initial: Locale = saved && supported.includes(saved) ? saved : 'zh'

const traditional: Record<string, string> = {
  'ICBC Admin': 'ICBC 管理後台', 'ICBC Road Test Booking': 'ICBC 路考預約',
  'Admin': '管理', 'Profile': '資料', 'Bookings': '任務', 'Settings': '設定', 'Log out': '登出',
  'Log in': '登入', 'Logging in…': '登入中…', 'Email': '電子郵件', 'Password': '密碼',
  'Register': '註冊', 'Registering…': '註冊中…', "Don't have an account? ": '還沒有帳號？',
  'Already have an account? ': '已有帳號？', 'Email is not verified. Go to verification?': '電子郵件未驗證，是否前往驗證？',
  'Login failed': '登入失敗', 'Registration failed': '註冊失敗', 'Passwords do not match': '兩次密碼不一致',
  'Password must be at least 8 characters': '密碼至少 8 個字元', 'Password (at least 8 characters)': '密碼（至少 8 個字元）',
  'Confirm password': '確認密碼', 'Verify email': '驗證電子郵件', 'Verify': '驗證',
  'Email verified': '驗證成功', '6-digit verification code': '6 位驗證碼',
  'Enter the 6-digit verification code': '請輸入 6 位驗證碼', 'Verification failed: ': '驗證失敗：',
  'Verification code resent': '驗證碼已重新發送', 'Send failed: ': '發送失敗：',
  'Resend code': '重新發送驗證碼', 'Back to login': '返回登入', 'Unknown error': '未知錯誤',
  'My Profile': '我的資料', 'Account': '帳號資訊', 'Role': '角色', 'User': '使用者',
  'Registered': '註冊時間', 'ICBC Profile': 'ICBC 資料', 'Licence number': '駕照號',
  'Licence number: ': '駕照號：', 'Last name': '姓氏', 'Last name: ': '姓氏：',
  'Exam class': '考試類型', 'Exam class: ': '考試類型：', 'Locations': '預選考點',
  'Location': '考點', 'Location: ': '考點：', 'Date range': '預約日期範圍', 'Dates: ': '日期：',
  'Any': '不限', 'to': '至', '— Not provided': '— 未填寫', '— Not configured': '— 未設定',
  'Edit profile / credentials': '編輯資料 / 修改憑證', 'ICBC Credentials': 'ICBC 登入憑證',
  'Configured': '已設定', 'Not configured': '未設定', 'Not configured; booking cannot start': '未設定，無法啟動預約',
  'Manage credentials': '管理憑證', 'Road Test Bookings': '預約任務', 'New Booking': '新增任務',
  'Create booking': '建立任務', 'My Bookings': '我的任務', 'Refresh': '重新整理',
  'No bookings': '暫無任務', 'Booking created and waiting for a worker': '任務已建立，等待 worker 執行',
  'Create failed: ': '建立失敗：', 'Failed to load bookings': '載入任務失敗',
  'Cancellation failed': '取消失敗', 'Cancel': '取消', 'Status': '狀態', 'Attempts': '嘗試',
  'Search rounds': '查詢輪次', 'Latest activity': '最近動態', 'Updated': '更新時間', 'Created': '建立時間',
  'Booking parameters come from Settings (location, dates, times, and preferences). Complete your profile and keyword before creating a booking.':
    '預約參數來自「設定」頁的資料（考點 / 日期 / 時間 / 偏好）。請先填寫資料與 keyword，再建立任務。',
  'ICBC profile saved': 'ICBC 資料已儲存', 'Save failed: ': '儲存失敗：',
  'End date cannot be earlier than start date': '結束日期不能早於開始日期',
  'End time must be later than start time': '結束時間必須晚於開始時間',
  'Booking settings saved': '預約設定已儲存', 'Keyword deleted': 'keyword 已刪除',
  'Delete failed: ': '刪除失敗：', 'Booking Settings': '預約設定',
  'ICBC login uses your last name, licence number, and keyword. The keyword is asymmetrically encrypted and cannot be decrypted by the server.':
    'ICBC 登入使用姓氏、駕照號和 keyword。keyword 使用非對稱加密儲存，伺服器無法解密。',
  'Configured; leave blank to keep it': '已設定；留空表示不修改', 'Enter keyword': '請輸入 keyword',
  'Encrypted and configured': '已加密設定', 'Save ICBC profile': '儲存 ICBC 資料',
  'Delete keyword': '刪除 keyword', 'Exam class (for example, 5 = Class 5)': '考試類型（例如 5 = 5 類車）',
  'Time range (start — end)': '時間區間（開始 — 結束）', 'Earliest date': '期望最早日期',
  'Latest date': '期望最晚日期', 'Select a location': '請選擇考點',
  'Preferred days': '星期偏好', 'Preferred time of day': '時段偏好', 'Morning': '上午',
  'Afternoon': '下午', 'Save booking settings': '儲存預約設定',
  'Delete the ICBC keyword? Booking cannot start without it.': '確定要刪除 ICBC keyword 嗎？刪除後無法啟動預約。',
  'Admin Console': '管理員控制台', 'All Users': '全部使用者', 'None': '暫無',
  'Email verification': '電子郵件驗證', 'Actions': '操作', 'Verified': '已驗證',
  'Not verified': '未驗證', 'Active': '啟用', 'Disabled': '停用',
  'Hide configuration': '收起設定', 'View configuration': '查看設定', 'Deleting…': '刪除中…',
  'Delete': '刪除', 'Protected': '受保護', 'Booking Range': '預約範圍',
  'Time Preferences': '時間偏好', 'Time range: ': '時間區間：', 'Days: ': '星期：',
  'Time of day: ': '時段：', 'All Bookings': '全部任務', 'Status filter:': '狀態篩選：',
  'All': '全部', 'Unknown user': '未知使用者', 'Failed to load admin data': '載入管理資料失敗',
  'Failed to delete user': '刪除使用者失敗', 'Mon': '週一', 'Tue': '週二', 'Wed': '週三',
  'Thu': '週四', 'Fri': '週五', 'Sat': '週六', 'Sun': '週日',
}

const french: Record<string, string> = {
  'ICBC Admin': 'Administration ICBC',
  'ICBC Road Test Booking': 'Réservation d’examen routier ICBC',
  'Admin': 'Administration', 'Profile': 'Profil', 'Bookings': 'Réservations',
  'Settings': 'Paramètres', 'Log out': 'Déconnexion',
  'Log in': 'Connexion', 'Logging in…': 'Connexion…', 'Email': 'Courriel',
  'Password': 'Mot de passe', 'Register': 'S’inscrire', 'Registering…': 'Inscription…',
  "Don't have an account? ": 'Pas encore de compte? ', 'Already have an account? ': 'Vous avez déjà un compte? ',
  'Email is not verified. Go to verification?': 'Le courriel n’est pas vérifié. Aller à la vérification?',
  'Login failed': 'Échec de la connexion', 'Registration failed': 'Échec de l’inscription',
  'Passwords do not match': 'Les mots de passe ne correspondent pas',
  'Password must be at least 8 characters': 'Le mot de passe doit contenir au moins 8 caractères',
  'Password (at least 8 characters)': 'Mot de passe (au moins 8 caractères)',
  'Confirm password': 'Confirmer le mot de passe',
  'Verify email': 'Vérifier le courriel', 'Verify': 'Vérifier', 'Email verified': 'Courriel vérifié',
  '6-digit verification code': 'Code de vérification à 6 chiffres',
  'Enter the 6-digit verification code': 'Entrez le code de vérification à 6 chiffres',
  'Verification failed: ': 'Échec de la vérification : ', 'Verification code resent': 'Code de vérification renvoyé',
  'Send failed: ': 'Échec de l’envoi : ', 'Resend code': 'Renvoyer le code', 'Back to login': 'Retour à la connexion',
  'Unknown error': 'Erreur inconnue', 'My Profile': 'Mon profil', 'Account': 'Compte',
  'Role': 'Rôle', 'User': 'Utilisateur', 'Registered': 'Inscrit le',
  'ICBC Profile': 'Profil ICBC', 'Licence number': 'Numéro de permis', 'Licence number: ': 'Numéro de permis : ',
  'Last name': 'Nom de famille', 'Last name: ': 'Nom de famille : ', 'Exam class': 'Classe d’examen',
  'Exam class: ': 'Classe d’examen : ', 'Locations': 'Centres', 'Location': 'Centre', 'Location: ': 'Centre : ',
  'Date range': 'Plage de dates', 'Dates: ': 'Dates : ', 'Any': 'Sans limite', 'to': 'à',
  '— Not provided': '— Non fourni', '— Not configured': '— Non configuré',
  'Edit profile / credentials': 'Modifier le profil / les identifiants', 'ICBC Credentials': 'Identifiants ICBC',
  'Configured': 'Configuré', 'Not configured': 'Non configuré',
  'Not configured; booking cannot start': 'Non configuré; la réservation ne peut pas démarrer',
  'Manage credentials': 'Gérer les identifiants', 'Road Test Bookings': 'Réservations d’examen routier',
  'New Booking': 'Nouvelle réservation', 'Create booking': 'Créer une réservation',
  'My Bookings': 'Mes réservations', 'Refresh': 'Actualiser', 'No bookings': 'Aucune réservation',
  'Booking created and waiting for a worker': 'Réservation créée, en attente d’un worker',
  'Create failed: ': 'Échec de la création : ', 'Failed to load bookings': 'Échec du chargement des réservations',
  'Cancellation failed': 'Échec de l’annulation', 'Cancel': 'Annuler', 'Status': 'État',
  'Attempts': 'Tentatives', 'Search rounds': 'Cycles de recherche', 'Latest activity': 'Activité récente',
  'Updated': 'Mis à jour', 'Created': 'Créé',
  'Booking parameters come from Settings (location, dates, times, and preferences). Complete your profile and keyword before creating a booking.':
    'Les paramètres proviennent des Paramètres (centre, dates, heures et préférences). Complétez votre profil et votre keyword avant de créer une réservation.',
  'ICBC profile saved': 'Profil ICBC enregistré', 'Save failed: ': 'Échec de l’enregistrement : ',
  'End date cannot be earlier than start date': 'La date de fin ne peut pas précéder la date de début',
  'End time must be later than start time': 'L’heure de fin doit être postérieure à l’heure de début',
  'Booking settings saved': 'Paramètres de réservation enregistrés', 'Keyword deleted': 'Keyword supprimé',
  'Delete failed: ': 'Échec de la suppression : ', 'Booking Settings': 'Paramètres de réservation',
  'ICBC login uses your last name, licence number, and keyword. The keyword is asymmetrically encrypted and cannot be decrypted by the server.':
    'La connexion ICBC utilise votre nom de famille, votre numéro de permis et votre keyword. Le keyword est chiffré de façon asymétrique et ne peut pas être déchiffré par le serveur.',
  'Configured; leave blank to keep it': 'Configuré; laissez vide pour le conserver', 'Enter keyword': 'Entrez le keyword',
  'Encrypted and configured': 'Chiffré et configuré', 'Save ICBC profile': 'Enregistrer le profil ICBC',
  'Delete keyword': 'Supprimer le keyword', 'Exam class (for example, 5 = Class 5)': 'Classe d’examen (par exemple, 5 = classe 5)',
  'Time range (start — end)': 'Plage horaire (début — fin)', 'Earliest date': 'Date la plus proche',
  'Latest date': 'Date la plus tardive', 'Select a location': 'Sélectionnez un centre',
  'Preferred days': 'Jours préférés', 'Preferred time of day': 'Période préférée',
  'Morning': 'Matin', 'Afternoon': 'Après-midi', 'Save booking settings': 'Enregistrer les paramètres',
  'Delete the ICBC keyword? Booking cannot start without it.': 'Supprimer le keyword ICBC? La réservation ne peut pas démarrer sans lui.',
  'Admin Console': 'Console d’administration', 'All Users': 'Tous les utilisateurs', 'None': 'Aucun',
  'Email verification': 'Vérification du courriel', 'Actions': 'Actions', 'Verified': 'Vérifié',
  'Not verified': 'Non vérifié', 'Active': 'Actif', 'Disabled': 'Désactivé',
  'Hide configuration': 'Masquer la configuration', 'View configuration': 'Voir la configuration',
  'Deleting…': 'Suppression…', 'Delete': 'Supprimer', 'Protected': 'Protégé',
  'Booking Range': 'Plage de réservation', 'Time Preferences': 'Préférences horaires',
  'Time range: ': 'Plage horaire : ', 'Days: ': 'Jours : ', 'Time of day: ': 'Période : ',
  'All Bookings': 'Toutes les réservations', 'Status filter:': 'Filtre d’état :', 'All': 'Tous',
  'Unknown user': 'Utilisateur inconnu', 'Failed to load admin data': 'Échec du chargement des données',
  'Failed to delete user': 'Échec de la suppression de l’utilisateur',
  'Mon': 'Lun', 'Tue': 'Mar', 'Wed': 'Mer', 'Thu': 'Jeu', 'Fri': 'Ven', 'Sat': 'Sam', 'Sun': 'Dim',
}

const spanish: Record<string, string> = {
  'ICBC Admin': 'Administración de ICBC', 'ICBC Road Test Booking': 'Reserva de examen de manejo ICBC',
  'Admin': 'Administración', 'Profile': 'Perfil', 'Bookings': 'Reservas', 'Settings': 'Configuración',
  'Log out': 'Cerrar sesión', 'Log in': 'Iniciar sesión', 'Logging in…': 'Iniciando sesión…',
  'Email': 'Correo electrónico', 'Password': 'Contraseña', 'Register': 'Registrarse', 'Registering…': 'Registrando…',
  "Don't have an account? ": '¿No tienes una cuenta? ', 'Already have an account? ': '¿Ya tienes una cuenta? ',
  'Email is not verified. Go to verification?': 'El correo no está verificado. ¿Ir a verificación?',
  'Login failed': 'Error al iniciar sesión', 'Registration failed': 'Error al registrarse',
  'Passwords do not match': 'Las contraseñas no coinciden',
  'Password must be at least 8 characters': 'La contraseña debe tener al menos 8 caracteres',
  'Password (at least 8 characters)': 'Contraseña (al menos 8 caracteres)', 'Confirm password': 'Confirmar contraseña',
  'Verify email': 'Verificar correo', 'Verify': 'Verificar', 'Email verified': 'Correo verificado',
  '6-digit verification code': 'Código de verificación de 6 dígitos',
  'Enter the 6-digit verification code': 'Ingresa el código de verificación de 6 dígitos',
  'Verification failed: ': 'Error de verificación: ', 'Verification code resent': 'Código reenviado',
  'Send failed: ': 'Error al enviar: ', 'Resend code': 'Reenviar código', 'Back to login': 'Volver al inicio de sesión',
  'Unknown error': 'Error desconocido', 'My Profile': 'Mi perfil', 'Account': 'Cuenta', 'Role': 'Rol',
  'User': 'Usuario', 'Registered': 'Registrado', 'ICBC Profile': 'Perfil de ICBC',
  'Licence number': 'Número de licencia', 'Licence number: ': 'Número de licencia: ',
  'Last name': 'Apellido', 'Last name: ': 'Apellido: ', 'Exam class': 'Clase de examen', 'Exam class: ': 'Clase de examen: ',
  'Locations': 'Centros', 'Location': 'Centro', 'Location: ': 'Centro: ', 'Date range': 'Rango de fechas',
  'Dates: ': 'Fechas: ', 'Any': 'Cualquiera', 'to': 'a', '— Not provided': '— No proporcionado',
  '— Not configured': '— No configurado', 'Edit profile / credentials': 'Editar perfil / credenciales',
  'ICBC Credentials': 'Credenciales de ICBC', 'Configured': 'Configurado', 'Not configured': 'No configurado',
  'Not configured; booking cannot start': 'No configurado; la reserva no puede comenzar',
  'Manage credentials': 'Administrar credenciales', 'Road Test Bookings': 'Reservas de examen de manejo',
  'New Booking': 'Nueva reserva', 'Create booking': 'Crear reserva', 'My Bookings': 'Mis reservas',
  'Refresh': 'Actualizar', 'No bookings': 'No hay reservas',
  'Booking created and waiting for a worker': 'Reserva creada y esperando un worker',
  'Create failed: ': 'Error al crear: ', 'Failed to load bookings': 'Error al cargar las reservas',
  'Cancellation failed': 'Error al cancelar', 'Cancel': 'Cancelar', 'Status': 'Estado', 'Attempts': 'Intentos',
  'Search rounds': 'Rondas de búsqueda', 'Latest activity': 'Actividad reciente', 'Updated': 'Actualizado', 'Created': 'Creado',
  'Booking parameters come from Settings (location, dates, times, and preferences). Complete your profile and keyword before creating a booking.':
    'Los parámetros provienen de Configuración (centro, fechas, horarios y preferencias). Completa tu perfil y keyword antes de crear una reserva.',
  'ICBC profile saved': 'Perfil de ICBC guardado', 'Save failed: ': 'Error al guardar: ',
  'End date cannot be earlier than start date': 'La fecha final no puede ser anterior a la fecha inicial',
  'End time must be later than start time': 'La hora final debe ser posterior a la hora inicial',
  'Booking settings saved': 'Configuración de reserva guardada', 'Keyword deleted': 'Keyword eliminado',
  'Delete failed: ': 'Error al eliminar: ', 'Booking Settings': 'Configuración de reserva',
  'ICBC login uses your last name, licence number, and keyword. The keyword is asymmetrically encrypted and cannot be decrypted by the server.':
    'El acceso a ICBC usa tu apellido, número de licencia y keyword. El keyword se cifra de forma asimétrica y el servidor no puede descifrarlo.',
  'Configured; leave blank to keep it': 'Configurado; deja en blanco para conservarlo', 'Enter keyword': 'Ingresa el keyword',
  'Encrypted and configured': 'Cifrado y configurado', 'Save ICBC profile': 'Guardar perfil de ICBC',
  'Delete keyword': 'Eliminar keyword', 'Exam class (for example, 5 = Class 5)': 'Clase de examen (por ejemplo, 5 = Clase 5)',
  'Time range (start — end)': 'Rango horario (inicio — fin)', 'Earliest date': 'Fecha más temprana',
  'Latest date': 'Fecha más tardía', 'Select a location': 'Selecciona un centro',
  'Preferred days': 'Días preferidos', 'Preferred time of day': 'Momento del día preferido',
  'Morning': 'Mañana', 'Afternoon': 'Tarde', 'Save booking settings': 'Guardar configuración',
  'Delete the ICBC keyword? Booking cannot start without it.': '¿Eliminar el keyword de ICBC? La reserva no puede comenzar sin él.',
  'Admin Console': 'Consola de administración', 'All Users': 'Todos los usuarios', 'None': 'Ninguno',
  'Email verification': 'Verificación de correo', 'Actions': 'Acciones', 'Verified': 'Verificado',
  'Not verified': 'No verificado', 'Active': 'Activo', 'Disabled': 'Desactivado',
  'Hide configuration': 'Ocultar configuración', 'View configuration': 'Ver configuración',
  'Deleting…': 'Eliminando…', 'Delete': 'Eliminar', 'Protected': 'Protegido',
  'Booking Range': 'Rango de reserva', 'Time Preferences': 'Preferencias horarias',
  'Time range: ': 'Rango horario: ', 'Days: ': 'Días: ', 'Time of day: ': 'Momento del día: ',
  'All Bookings': 'Todas las reservas', 'Status filter:': 'Filtro de estado:', 'All': 'Todos',
  'Unknown user': 'Usuario desconocido', 'Failed to load admin data': 'Error al cargar los datos',
  'Failed to delete user': 'Error al eliminar el usuario',
  'Mon': 'Lun', 'Tue': 'Mar', 'Wed': 'Mié', 'Thu': 'Jue', 'Fri': 'Vie', 'Sat': 'Sáb', 'Sun': 'Dom',
}

const translations: Record<'zh-Hant' | 'fr' | 'es', Record<string, string>> = {
  'zh-Hant': traditional, fr: french, es: spanish,
}
const locale = ref<Locale>(initial)
document.documentElement.lang = initial === 'zh' ? 'zh-CN' : initial === 'zh-Hant' ? 'zh-TW' : initial

watch(locale, (value) => {
  localStorage.setItem('icbc.locale', value)
  document.documentElement.lang = value === 'zh' ? 'zh-CN' : value === 'zh-Hant' ? 'zh-TW' : value
})

export function useI18n() {
  const isEnglish = computed(() => locale.value === 'en')
  const dateLocale = computed(() => ({ zh: 'zh-CN', 'zh-Hant': 'zh-TW', en: 'en-CA', fr: 'fr-CA', es: 'es-ES' })[locale.value])

  function tr(chinese: string, english: string, frenchText?: string, spanishText?: string, traditionalText?: string): string {
    if (locale.value === 'zh') return chinese
    if (locale.value === 'zh-Hant') return traditionalText || translations['zh-Hant'][english] || chinese
    if (locale.value === 'en') return english
    if (locale.value === 'fr') return frenchText || translations.fr[english] || english
    return spanishText || translations.es[english] || english
  }

  function apiError(error: any, chinese: string, english: string): string {
    if (locale.value === 'zh') return error.response?.data?.detail || chinese
    return tr(chinese, english)
  }

  return { locale, isEnglish, dateLocale, tr, apiError }
}
