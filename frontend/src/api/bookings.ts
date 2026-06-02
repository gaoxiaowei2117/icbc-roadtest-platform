import { api } from './client'

export interface Booking {
  id: number
  user_id: number
  status: 'pending' | 'running' | 'done' | 'failed' | 'cancelled'
  target_date: string | null
  time_window: Record<string, unknown> | null
  pos_code: string | null
  attempt_count: number
  last_error: string | null
  result: Record<string, unknown> | null
  started_at: string | null
  finished_at: string | null
  created_at: string
  updated_at: string
}

export async function listBookings(): Promise<Booking[]> {
  return (await api.get('/api/bookings')).data
}

export async function createBooking(payload: {
  target_date?: string
  time_window?: Record<string, unknown>
  pos_code?: string
}): Promise<Booking> {
  return (await api.post('/api/bookings', payload)).data
}

export async function cancelBooking(id: number): Promise<Booking> {
  return (await api.post(`/api/bookings/${id}/cancel`)).data
}
