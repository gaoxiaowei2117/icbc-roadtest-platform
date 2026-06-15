import { defineStore } from 'pinia'
import axios from 'axios'
import { ref, computed } from 'vue'

export interface User {
  id: number
  email: string
  is_admin: boolean
  icbc_license_no: string | null
  icbc_last_name: string | null
  exam_class: string | null
  pos_ids: number[] | null
  expect_after_date: string | null
  expect_before_date: string | null
  expect_time_range: string | null
  pref_days_of_week: number[] | null
  pref_parts_of_day: number[] | null
  created_at: string
}

const ACCESS_KEY = 'icbc.access'
const REFRESH_KEY = 'icbc.refresh'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(ACCESS_KEY))
  const refreshToken = ref<string | null>(localStorage.getItem(REFRESH_KEY))
  const user = ref<User | null>(null)

  const isLoggedIn = computed(() => !!token.value)

  axios.defaults.baseURL = ''
  axios.interceptors.request.use((cfg) => {
    if (token.value) cfg.headers.Authorization = `Bearer ${token.value}`
    return cfg
  })
  axios.interceptors.response.use(
    (r) => r,
    async (err) => {
      if (err.response?.status === 401 && refreshToken.value && !err.config._retry) {
        err.config._retry = true
        try {
          const r = await axios.post('/api/auth/refresh', { refresh_token: refreshToken.value })
          setTokens(r.data.access_token, refreshToken.value)
          err.config.headers.Authorization = `Bearer ${r.data.access_token}`
          return axios(err.config)
        } catch {
          logout()
        }
      }
      return Promise.reject(err)
    },
  )

  function setTokens(access: string, refresh: string) {
    token.value = access
    refreshToken.value = refresh
    localStorage.setItem(ACCESS_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
  }

  async function login(email: string, password: string) {
    const r = await axios.post('/api/auth/login', { email, password })
    setTokens(r.data.access_token, r.data.refresh_token)
    await fetchMe()
  }

  async function register(email: string, password: string) {
    const r = await axios.post('/api/auth/register', { email, password })
    setTokens(r.data.access_token, r.data.refresh_token)
    await fetchMe()
  }

  async function fetchMe() {
    const r = await axios.get('/api/users/me')
    user.value = r.data
  }

  async function logout() {
    token.value = null
    refreshToken.value = null
    user.value = null
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  }

  return { token, refreshToken, user, isLoggedIn, login, register, fetchMe, logout, setTokens }
})
