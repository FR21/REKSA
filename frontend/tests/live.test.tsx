import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { WorkerCard } from '../src/components/workers/WorkerCard'
import { useLiveStore } from '../src/stores/liveStore'
import type { Worker } from '../src/types'
import { filterWorkers } from '../src/utils/filterWorkers'

const worker: Worker = {
  id: 'W01', name: 'Andi Pratama', role: 'Operator', area: 'Gudang Utama', risk_score: 88,
  risk_level: 'CRITICAL', closest_hazard: 'F01', hazard_name: 'Forklift Alpha',
  hazard_type: 'FORKLIFT', hazard_status: 'MOVING', rssi: -40, smoothed_rssi: -42,
  proximity: 'CRITICAL', exposure_seconds: 8, movement: 'BERGERAK', impact: false,
  fall_detected: false, impact_g: 1.1, mq135_raw: 900, air_quality_level: 'NORMAL', gas_alert: false,
  temperature: 31, humidity: 70, online: true, last_update: new Date().toISOString(),
  x: 40, y: 40, calculation_source: 'RULE_BASED_SCORING', dominant_factor: 'Paparan bahaya',
  recommended_action: 'Jauhkan pekerja.',
}

describe('live monitoring behavior', () => {
  beforeEach(() => useLiveStore.setState({ workers: [], notificationCount: 0, lastEventId: null }))

  it('renders restrained critical alert and mark-safe action', () => {
    render(<MemoryRouter><WorkerCard worker={worker} onMarkSafe={() => undefined} /></MemoryRouter>)
    expect(screen.getByText('TINDAKAN SEGERA DIPERLUKAN')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Tandai Aman' })).toBeInTheDocument()
  })

  it('filters by search, risk, and device status', () => {
    const offline = { ...worker, id: 'W02', name: 'Siti Rahma', risk_level: 'SAFE' as const, online: false }
    expect(filterWorkers([worker, offline], 'andi', 'CRITICAL', 'ONLINE')).toEqual([worker])
    expect(filterWorkers([worker, offline], '', 'SAFE', 'OFFLINE')).toEqual([offline])
  })

  it('updates worker state and deduplicates websocket event IDs', () => {
    useLiveStore.getState().setWorkers([worker])
    useLiveStore.getState().updateWorker({ ...worker, risk_score: 93 })
    expect(useLiveStore.getState().workers[0].risk_score).toBe(93)
    expect(useLiveStore.getState().registerEvent('event-1', true)).toBe(true)
    expect(useLiveStore.getState().registerEvent('event-1', true)).toBe(false)
    expect(useLiveStore.getState().notificationCount).toBe(1)
  })
})
