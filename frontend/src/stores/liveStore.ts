import { create } from 'zustand'
import type { VoiceTransmission, Worker } from '../types'

export interface NotificationItem {
  id: string
  message: string
  time: string
  read: boolean
}

interface LiveState {
  workers: Worker[]
  wsStatus: 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED'
  lastEventId: string | null
  notificationCount: number
  notifications: NotificationItem[]
  voiceTransmissions: VoiceTransmission[]
  latestTransmission: VoiceTransmission | null
  setWorkers: (workers: Worker[]) => void
  updateWorker: (worker: Worker) => void
  deleteWorker: (id: string) => void
  setWsStatus: (status: LiveState['wsStatus']) => void
  setVoiceTransmissions: (items: VoiceTransmission[]) => void
  addVoiceTransmission: (item: VoiceTransmission) => void
  acknowledgeVoiceTransmission: (id: string, note?: string) => void
  registerEvent: (id: string, critical?: boolean, payload?: { event?: string; data?: Record<string, unknown> } | null) => boolean
  clearNotifications: () => void
  markAllRead: () => void
}

export const useLiveStore = create<LiveState>((set, get) => ({
  workers: [],
  wsStatus: 'RECONNECTING',
  lastEventId: null,
  notificationCount: 0,
  notifications: [],
  voiceTransmissions: [],
  latestTransmission: null,
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
  setVoiceTransmissions: (voiceTransmissions) =>
    set({
      voiceTransmissions,
      latestTransmission: voiceTransmissions.find((t) => !t.acknowledged) || null,
    }),
  addVoiceTransmission: (item) =>
    set((state) => ({
      voiceTransmissions: [item, ...state.voiceTransmissions.filter((t) => t.id !== item.id)].slice(0, 40),
      latestTransmission: item,
    })),
  acknowledgeVoiceTransmission: (id, note) =>
    set((state) => {
      const updated = state.voiceTransmissions.map((t) =>
        t.id === id ? { ...t, acknowledged: true, supervisor_note: note ?? t.supervisor_note } : t
      )
      const nextActive = updated.find((t) => !t.acknowledged) || null
      return {
        voiceTransmissions: updated,
        latestTransmission: nextActive,
      }
    }),
  registerEvent: (id, critical = false, payload: { event?: string; data?: Record<string, unknown> } | null = null) => {
    if (get().lastEventId === id) return false
    set((state) => {
      let newCount = state.notificationCount
      const newNotifs = [...state.notifications]
      
      const isTestWarning =
        payload?.event === 'warning.created' &&
        (Boolean(payload?.data?.is_test) || /uji|test/i.test(String(payload?.data?.reason ?? '')))

      if (!isTestWarning && (critical || payload?.event === 'voice.command' || payload?.event === 'voice.transmission')) {
        newCount += 1
        let msg = ''
        
        if (payload?.event === 'voice.transmission') {
          const transcription = payload?.data?.transcription || '(suara tidak jelas)'
          const workerName = payload?.data?.worker_name || payload?.data?.worker_id || 'Pekerja'
          const label = payload?.data?.intent_label || 'Transmisi Suara'
          msg = `🎙️ [${workerName}] ${label}: "${transcription}"`
        } else if (payload?.event === 'voice.command') {
          const transcription = payload?.data?.transcription || '(suara tidak jelas)'
          const workerId = payload?.data?.worker_id || 'Unknown Worker'
          msg = `🎙️ [${workerId}] Suara: "${transcription}"`
        } else if (payload?.event === 'warning.created') {
          const reason = String(payload?.data?.reason || '')
          const workerId = String(payload?.data?.worker_id || 'helm')
          if (/Alarm Balasan Suara|Buzzer/i.test(reason)) {
            msg = `🔊 Alarm buzzer dikirim ke helm ${workerId}`
          } else {
            msg = `⚠️ Peringatan dikirim ke ${workerId}: ${reason || 'Bahaya terdeteksi'}`
          }
        } else if (payload?.event === 'near_miss.created') {
          const workerName = payload?.data?.worker_name || payload?.data?.worker_id || 'Pekerja'
          const hazardName = payload?.data?.hazard_name || 'Bahaya'
          msg = `🚨 Near Miss [${workerName}]: Mendekati ${hazardName}`
        } else {
          msg = '⚠️ Peringatan sistem K3'
        }
        
        newNotifs.unshift({
          id,
          message: msg,
          time: new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
          read: false
        })
        if (newNotifs.length > 8) newNotifs.pop()
      }
      return { lastEventId: id, notificationCount: Math.min(newCount, 99), notifications: newNotifs }
    })
    return true
  },
  clearNotifications: () => set({ 
    notificationCount: 0,
    notifications: []
  }),
  markAllRead: () => set((state) => ({
    notificationCount: 0,
    notifications: state.notifications.map((n) => ({ ...n, read: true }))
  })),
}))

