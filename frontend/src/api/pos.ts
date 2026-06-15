import { api } from './client'

export interface PosEntry {
  name: string
  pos_id: number
}

export async function getPosList(): Promise<PosEntry[]> {
  return (await api.get('/api/pos-list')).data
}
