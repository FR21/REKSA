import { useState, useCallback, useMemo } from 'react'
import type { Worker, Hazard } from '../types'

export const DEFAULT_ROLES = [
  'Operator Forklift',
  'Operator Laser Cutter',
  'Teknisi Elektrikal',
  'Supervisor Area',
  'Safety Officer',
  'Operator Umum',
]

export const DEFAULT_AREAS = [
  'Gudang Utama',
  'Zona Bongkar',
  'Produksi A',
  'Produksi B',
  'Area Laser',
  'Koridor Timur',
  'Bengkel / Workshop',
  'Loading Dock',
  'Laboratorium Uji',
]

const ROLES_STORAGE_KEY = 'reksa_custom_roles'
const AREAS_STORAGE_KEY = 'reksa_custom_areas'

function readStorage(key: string): string[] {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function useCatalogOptions(workers: Worker[] = [], hazards: Hazard[] = []) {
  const [customRoles, setCustomRoles] = useState<string[]>(() => readStorage(ROLES_STORAGE_KEY))
  const [customAreas, setCustomAreas] = useState<string[]>(() => readStorage(AREAS_STORAGE_KEY))

  const roles = useMemo(() => {
    const set = new Set<string>()
    DEFAULT_ROLES.forEach((r) => set.add(r))
    customRoles.forEach((r) => r.trim() && set.add(r.trim()))
    workers.forEach((w) => w.role?.trim() && set.add(w.role.trim()))
    return Array.from(set)
  }, [customRoles, workers])

  const areas = useMemo(() => {
    const set = new Set<string>()
    DEFAULT_AREAS.forEach((a) => set.add(a))
    customAreas.forEach((a) => a.trim() && set.add(a.trim()))
    workers.forEach((w) => w.area?.trim() && set.add(w.area.trim()))
    hazards.forEach((h) => h.area?.trim() && set.add(h.area.trim()))
    return Array.from(set)
  }, [customAreas, workers, hazards])

  const addRole = useCallback((newRole: string) => {
    const clean = newRole.trim()
    if (!clean) return
    setCustomRoles((prev) => {
      if (prev.includes(clean)) return prev
      const next = [...prev, clean]
      try {
        localStorage.setItem(ROLES_STORAGE_KEY, JSON.stringify(next))
      } catch {
        // ignore quota error
      }
      return next
    })
  }, [])

  const addArea = useCallback((newArea: string) => {
    const clean = newArea.trim()
    if (!clean) return
    setCustomAreas((prev) => {
      if (prev.includes(clean)) return prev
      const next = [...prev, clean]
      try {
        localStorage.setItem(AREAS_STORAGE_KEY, JSON.stringify(next))
      } catch {
        // ignore quota error
      }
      return next
    })
  }, [])

  return { roles, areas, addRole, addArea }
}
