import { api } from './client'

export interface Booking {
  id: number
  user_id: number
  user_email?: string
  status: 'awaiting_payment' | 'awaiting_review' | 'payment_rejected' | 'pending' | 'running' | 'done' | 'failed' | 'cancelled'
  payment_status: 'not_required' | 'awaiting_payment' | 'awaiting_review' | 'approved' | 'rejected'
  payment_reference: string | null
  payment_submitted_at: string | null
  reviewed_at: string | null
  review_reason: string | null
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

export async function submitPayment(id: number, paymentReference?: string): Promise<Booking> {
  return (await api.post(`/api/bookings/${id}/payment-submitted`, {
    payment_reference: paymentReference || null,
  })).data
}

export async function cancelBooking(id: number): Promise<Booking> {
  return (await api.post(`/api/bookings/${id}/cancel`)).data
}
