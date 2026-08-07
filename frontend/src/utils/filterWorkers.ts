import type { Worker } from '../types'

export function filterWorkers(workers: Worker[], search: string, risk: string, device: string) {
  return workers
    .filter((worker) =>
      (!search || `${worker.name} ${worker.id}`.toLowerCase().includes(search.toLowerCase())) &&
      (risk === 'ALL' || worker.risk_level === risk) &&
      (device === 'ALL' || (device === 'ONLINE') === worker.online),
    )
    .sort((a, b) => b.risk_score - a.risk_score)
}
