import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { VoiceTransmission, Worker } from '../types'
import { useLiveStore } from '../stores/liveStore'

interface LiveEvent {
  event: string
  timestamp?: string
  data: unknown
}

export function useLiveSocket() {
  const queryClient = useQueryClient()
  const updateWorker = useLiveStore((state) => state.updateWorker)
  const setWorkers = useLiveStore((state) => state.setWorkers)
  const deleteWorker = useLiveStore((state) => state.deleteWorker)
  const setWsStatus = useLiveStore((state) => state.setWsStatus)
  const registerEvent = useLiveStore((state) => state.registerEvent)
  const addVoiceTransmission = useLiveStore((state) => state.addVoiceTransmission)

  useEffect(() => {
    let socket: WebSocket | undefined
    let retry = 0
    let cancelled = false
    let heartbeat: number | undefined
    const base = import.meta.env.VITE_WS_URL || `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/live`

    const connect = () => {
      if (cancelled) return
      setWsStatus(retry ? 'RECONNECTING' : 'DISCONNECTED')
      socket = new WebSocket(base)
      socket.onopen = () => {
        retry = 0
        setWsStatus('CONNECTED')
        heartbeat = window.setInterval(() => socket?.readyState === WebSocket.OPEN && socket.send('ping'), 15_000)
      }
      socket.onmessage = (message) => {
        const envelope = JSON.parse(message.data as string) as LiveEvent
        const id = `${envelope.event}-${envelope.timestamp ?? JSON.stringify(envelope.data).slice(0, 40)}`
        if (!registerEvent(id, envelope.event === 'near_miss.created' || envelope.event === 'warning.created' || envelope.event === 'voice.command' || envelope.event === 'voice.transmission', envelope as { event?: string; data?: Record<string, unknown> })) return
        if (envelope.event === 'worker.updated') {
          const data = envelope.data as Worker | { workers?: Worker[] }
          if ('workers' in data && Array.isArray(data.workers)) setWorkers(data.workers)
          else updateWorker(data as Worker)
          void queryClient.invalidateQueries({ queryKey: ['workers'] })
          void queryClient.invalidateQueries({ queryKey: ['summary'] })
          void queryClient.invalidateQueries({ queryKey: ['dashboard-live'] })
          void queryClient.invalidateQueries({ queryKey: ['risk-trend'] })
          void queryClient.invalidateQueries({ queryKey: ['activity'] })
        }
        if (envelope.event === 'voice.transmission') {
          addVoiceTransmission(envelope.data as VoiceTransmission)
          void queryClient.invalidateQueries({ queryKey: ['voice-transmissions'] })
        }
        if (envelope.event === 'worker.deleted') deleteWorker((envelope.data as { id: string }).id)
        if (envelope.event === 'profile.updated') {
          void queryClient.invalidateQueries({ queryKey: ['profile'] })
        }
        if (envelope.event === 'voice.transmission_acknowledged') {
          const trans = envelope.data as VoiceTransmission
          if (trans?.id) {
            useLiveStore.getState().acknowledgeVoiceTransmission(trans.id, trans.supervisor_note)
          }
          void queryClient.invalidateQueries({ queryKey: ['voice-transmissions'] })
        }
        if (envelope.event === 'voice.transmission_updated') {
          const trans = envelope.data as VoiceTransmission
          if (trans?.id) {
            useLiveStore.getState().updateVoiceTransmission(trans)
          }
          void queryClient.invalidateQueries({ queryKey: ['voice-transmissions'] })
        }
        if (['near_miss.created', 'near_miss.acknowledged', 'warning.created', 'simulation.status_changed', 'worker.deleted', 'device.deleted', 'device.paired', 'voice.transmission_acknowledged'].includes(envelope.event)) {
          void queryClient.invalidateQueries()
        }
      }
      socket.onerror = () => socket?.close()
      socket.onclose = () => {
        if (heartbeat) clearInterval(heartbeat)
        setWsStatus('RECONNECTING')
        const delay = Math.min(30_000, 1000 * 2 ** retry++)
        window.setTimeout(connect, delay)
      }
    }
    connect()
    return () => {
      cancelled = true
      if (heartbeat) clearInterval(heartbeat)
      socket?.close()
    }
  }, [queryClient, registerEvent, setWsStatus, setWorkers, updateWorker, deleteWorker, addVoiceTransmission])
}
