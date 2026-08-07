import { create } from 'zustand'
import type { Worker } from '../types'

interface LiveState {
  workers: Worker[]
  wsStatus: 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED'
  lastEventId: string | null
  notificationCount: number
  setWorkers: (workers: Worker[]) => void
  updateWorker: (worker: Worker) => void
  deleteWorker: (id: string) => void
  setWsStatus: (status: LiveState['wsStatus']) => void
  registerEvent: (id: string, critical?: boolean) => boolean
  clearNotifications: () => void
}

export const useLiveStore = create<LiveState>((set, get) => ({
  workers: [],
  wsStatus: 'RECONNECTING',
  lastEventId: null,
  notificationCount: 0,
  setWorkers: (workers) => set({ workers }),
  updateWorker: (worker) =>
    set((state) => {
      const exists = state.workers.some((item) => item.id === worker.id)
      return {
        workers: exists
          ? state.workers.map((item) => (item.id === worker.id ? { ...item, ...worker } : item))
          : [worker, ...state.workers]
      }
    }),
  deleteWorker: (id) =>
    set((state) => ({ workers: state.workers.filter((item) => item.id !== id) })),
  setWsStatus: (wsStatus) => set({ wsStatus }),
  registerEvent: (id, critical = false) => {
    if (get().lastEventId === id) return false
    set((state) => ({ lastEventId: id, notificationCount: state.notificationCount + (critical ? 1 : 0) }))
    return true
  },
  clearNotifications: () => set({ notificationCount: 0 }),
}))

