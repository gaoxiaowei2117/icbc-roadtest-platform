import { api } from './client'

export interface Booking {
  id: number
  user_id: number
  user_email?: string
  status: 'pending' | 'running' | 'done' | 'failed' | 'cancelled'
  attempt_count: number
  progress_rounds: number
  last_progress: string | null
  last_progress_at: string | null
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

export async function createBooking() {
  return (await api.post('/api/bookings', {})).data
}

export async function cancelBooking(id: number): Promise<Booking> {
  return (await api.post(`/api/bookings/${id}/cancel`)).data
}
