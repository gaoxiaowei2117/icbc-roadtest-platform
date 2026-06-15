import { api } from './client'
import type { User } from '@/stores/auth'

export async function getMe(): Promise<User> {
  return (await api.get('/api/users/me')).data
}

export async function updateMe(payload: Partial<User>): Promise<User> {
  return (await api.patch('/api/users/me', payload)).data
}

export async function getSecretStatus(): Promise<{ has_secret: boolean; updated_at: string | null }> {
  return (await api.get('/api/users/me/secret')).data
}

export async function setSecret(payload: { keyword: string }) {
  return (await api.put('/api/users/me/secret', payload)).data
}

export async function deleteSecret() {
  return (await api.delete('/api/users/me/secret')).data
}
