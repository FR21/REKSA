import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Search, Plus, Trash2, ArrowRight, Shield, Activity, HardHat, Users } from 'lucide-react'
import { api, getErrorMessage } from '../services/api'
import { LoadingState, ErrorState, EmptyState } from '../components/common/States'
import { Panel } from '../components/common/Panel'
import { KpiCard } from '../components/dashboard/KpiCard'
import type { Worker, Device } from '../types'

export default function WorkersPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')

  const [workerId, setWorkerId] = useState('')
  const [name, setName] = useState('')
  const [role, setRole] = useState('Operator')
  const [area, setArea] = useState('Gudang Utama')
  const [successMsg, setSuccessMsg] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  const workersQuery = useQuery({
    queryKey: ['workers'],
    queryFn: () => api<{ items: Worker[] }>('/workers')
  })

  const devicesQuery = useQuery({
    queryKey: ['devices'],
    queryFn: () => api<{ items: Device[] }>('/devices')
  })

  const createWorkerMutation = useMutation({
    mutationFn: (data: { id: string; name: string; role: string; area: string }) =>
      api<{ worker: Worker; message: string }>('/workers', {
        method: 'POST',
        body: JSON.stringify(data)
      }),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: ['workers'] })
      setSuccessMsg(res.message || 'Worker successfully registered!')
      setErrorMsg('')
      setWorkerId('')
      setName('')
      setTimeout(() => setSuccessMsg(''), 3000)
    },
    onError: (err: unknown) => {
      setErrorMsg(getErrorMessage(err, 'Failed to register worker'))
      setSuccessMsg('')
    }
  })

  const deleteWorkerMutation = useMutation({
    mutationFn: (id: string) =>
      api<{ message: string }>('/workers/' + id, {
        method: 'DELETE'
      }),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: ['workers'] })
      setSuccessMsg(res.message || 'Worker deleted successfully.')
      setErrorMsg('')
      setTimeout(() => setSuccessMsg(''), 3000)
    },
    onError: (err: unknown) => {
      setErrorMsg(getErrorMessage(err, 'Failed to delete worker'))
      setSuccessMsg('')
    }
  })

  const handleRegisterSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!workerId || !name) {
      setErrorMsg('Worker ID dan Nama Pekerja wajib diisi.')
      return
    }
    createWorkerMutation.mutate({
      id: workerId.trim().toUpperCase(),
      name: name.trim(),
      role,
      area
    })
  }

  const handleDeleteClick = (id: string, workerName: string) => {
    if (window.confirm(`Apakah Anda yakin ingin menghapus pekerja ${workerName} (${id})?`)) {
      deleteWorkerMutation.mutate(id)
    }
  }

  const filteredWorkers = workersQuery.data?.items.filter((w) =>
    w.name.toLowerCase().includes(search.toLowerCase()) ||
    w.id.toLowerCase().includes(search.toLowerCase()) ||
    w.role.toLowerCase().includes(search.toLowerCase())
  ) ?? []

  if (workersQuery.isLoading) return <LoadingState label="Memuat data pekerja..." />
  if (workersQuery.isError) return <ErrorState retry={() => void workersQuery.refetch()} />

  const totalWorkers = workersQuery.data?.items.length ?? 0
  const onlineCount = workersQuery.data?.items.filter((w) => w.online).length ?? 0
  const avgRisk = totalWorkers > 0 
    ? Math.round(workersQuery.data!.items.reduce((sum, w) => sum + w.risk_score, 0) / totalWorkers) 
    : 0

  return (
    <div className="stack-lg wide-page workers-page">
      <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', marginBottom: '8px' }}>
        <KpiCard label="TOTAL WORKFORCE" value={totalWorkers} detail="Terdaftar dalam sistem" icon={Users} tone="blue" />
        <KpiCard label="ACTIVE HELMETS" value={onlineCount} detail={`${totalWorkers - onlineCount} perangkat offline`} icon={HardHat} tone="green" />
        <KpiCard label="AVERAGE RISK LEVEL" value={avgRisk} unit="%" detail="Status kumulatif: Aman" icon={Shield} tone="orange" />
      </div>

      <div className="device-registry-grid">
        <div className="stack-md">
          <Panel
            title="Workforce Directory"
            subtitle="Daftar administratif personel plant dan status perangkat keselamatan mereka"
            className="workforce-panel"
            action={
              <div className="search-box">
                <Search size={16} />
                <input
                  type="text"
                  placeholder="Cari nama, ID, atau jabatan..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
            }
          >
            {filteredWorkers.length === 0 ? (
              <EmptyState label="Tidak ada pekerja yang cocok dengan pencarian Anda." />
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Pekerja</th>
                      <th>Jabatan</th>
                      <th>Area Penugasan</th>
                      <th>Paired Device</th>
                      <th>Status</th>
                      <th style={{ textAlign: 'right' }}>Aksi</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredWorkers.map((w) => {
                      const matchedDevice = devicesQuery.data?.items.find(
                        (d) => d.type === 'SMART_HELMET' && d.topic.includes(`/helmet/${w.id}/`)
                      )
                      return (
                        <tr key={w.id}>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                              <div className="avatar small">
                                {w.name.split(' ').map((p) => p[0]).slice(0, 2).join('')}
                              </div>
                              <div>
                                <strong>{w.name}</strong>
                                <small style={{ color: 'var(--muted)' }}>{w.id}</small>
                              </div>
                            </div>
                          </td>
                          <td>{w.role}</td>
                          <td>{w.area}</td>
                          <td>
                            {matchedDevice ? (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '13px', fontWeight: 600, color: 'var(--text)' }}>
                                <HardHat size={14} style={{ color: 'var(--blue)' }} /> {matchedDevice.id}
                              </span>
                            ) : (
                              <span style={{ fontSize: '13px', color: 'var(--muted)' }}>No Helmet paired</span>
                            )}
                          </td>
                          <td>
                            <span className={`online-label ${!w.online ? 'offline' : ''}`}>
                              <i /> {w.online ? 'Online' : 'Offline'}
                            </span>
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            <div style={{ display: 'inline-flex', gap: '8px' }}>
                              <Link
                                to={`/workers/${w.id}`}
                                className="action-btn"
                                style={{ color: 'var(--blue)' }}
                                title="Lihat Profil Risiko"
                              >
                                <ArrowRight size={16} />
                              </Link>
                              <button
                                className="action-btn danger-btn"
                                style={{ color: '#ef4444' }}
                                title="Hapus Pekerja"
                                onClick={() => handleDeleteClick(w.id, w.name)}
                              >
                                <Trash2 size={15} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>

        <div className="device-form-panel">
          <h3>Pendaftaran Pekerja Baru</h3>
          <p style={{ fontSize: '13px', color: 'var(--muted)', margin: '-10px 0 20px 0', lineHeight: 1.4 }}>
            Daftarkan personel baru ke dalam sistem untuk dipasangkan dengan Smart Helmet.
          </p>

          <form onSubmit={handleRegisterSubmit} className="device-form">
            <label>
              <span>ID Pekerja (Format W-XX)</span>
              <input
                type="text"
                placeholder="e.g. W07"
                value={workerId}
                onChange={(e) => setWorkerId(e.target.value)}
                required
              />
            </label>

            <label>
              <span>Nama Lengkap Pekerja</span>
              <input
                type="text"
                placeholder="e.g. Fajar Hidayat"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </label>

            <label>
              <span>Jabatan / Peran K3</span>
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="Operator Forklift">Operator Forklift</option>
                <option value="Operator Laser Cutter">Operator Laser Cutter</option>
                <option value="Teknisi Elektrikal">Teknisi Elektrikal</option>
                <option value="Supervisor Area">Supervisor Area</option>
                <option value="Safety Officer">Safety Officer</option>
                <option value="Operator Umum">Operator Umum</option>
              </select>
            </label>

            <label>
              <span>Area Kerja Utama</span>
              <select value={area} onChange={(e) => setArea(e.target.value)}>
                <option value="Gudang Utama">Gudang Utama</option>
                <option value="Produksi A">Produksi A</option>
                <option value="Produksi B">Produksi B</option>
                <option value="Loading Dock">Loading Dock</option>
                <option value="Laboratorium Uji">Laboratorium Uji</option>
              </select>
            </label>

            {successMsg && (
              <div style={{ color: '#059669', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
                <Activity size={16} /> {successMsg}
              </div>
            )}

            {errorMsg && (
              <div style={{ color: '#ef4444', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
                <Shield size={16} /> {errorMsg}
              </div>
            )}

            <button
              type="submit"
              className="button primary"
              disabled={createWorkerMutation.isPending}
              style={{ width: '100%' }}
            >
              <Plus size={16} /> {createWorkerMutation.isPending ? 'Mendaftarkan...' : 'Daftarkan Pekerja'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
