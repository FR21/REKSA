import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, Radio, Save, Thermometer, Wifi, ShieldAlert, Plus, RefreshCw, Edit2, Trash2 } from 'lucide-react'
import { api, getErrorMessage } from '../services/api'
import { ErrorState, LoadingState } from '../components/common/States'
import type { Device, Worker, Hazard } from '../types'
import { Panel } from '../components/common/Panel'
import { formatDate } from '../lib/utils'

type Settings = Record<string, number>
type DeviceType = 'SMART_HELMET' | 'HAZARD_NODE' | 'ENVIRONMENT_NODE'

export default function SettingsPage() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'system' | 'devices'>('system')

  // --- SYSTEM SETTINGS TAB ---
  const query = useQuery({ queryKey: ['settings'], queryFn: () => api<{ values: Settings }>('/settings') })
  const [values, setValues] = useState<Settings>({})
  const [confirmed, setConfirmed] = useState(false)
  const mutation = useMutation({
    mutationFn: () => api<{ values: Settings; message: string }>('/settings', {
      method: 'PATCH',
      body: JSON.stringify({ ...values, confirmed: true })
    }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['settings'] })
    }
  })

  useEffect(() => { if (query.data) setValues(query.data.values) }, [query.data])

  const clearMutation = useMutation({
    mutationFn: () => api<{ status: string }>('/simulation/reset', { method: 'POST' }),
    onSuccess: (res) => {
      void queryClient.invalidateQueries()
      alert(res.status ? 'Data demo berhasil dikembalikan.' : 'Data demo berhasil direset.')
    },
    onError: (err: unknown) => {
      alert(getErrorMessage(err, 'Gagal reset data demo'))
    }
  })

  const handleClearSimulationData = () => {
    if (window.confirm('Reset data demo ke kondisi awal? Daftar worker, forklift, hazard, device, dan near-miss akan dikembalikan ke seed bawaan.')) {
      clearMutation.mutate()
    }
  }

  const update = (key: string, value: string) => setValues((current) => ({ ...current, [key]: Number(value) }))

  const sections = [
    { title: 'Proximity Thresholds', subtitle: 'Klasifikasi zona berdasarkan smoothed RSSI.', icon: Radio, fields: [['moderate_rssi','Moderate RSSI','dBm'],['high_rssi','High RSSI','dBm'],['critical_rssi','Critical RSSI','dBm'],['critical_exposure_duration','Critical Exposure','detik']] },
    { title: 'Warning & Connectivity', subtitle: 'Keterlambatan perangkat dan cooldown peringatan.', icon: Wifi, fields: [['device_offline_timeout','Device Offline Timeout','detik'],['warning_cooldown','Warning Cooldown','detik']] },
    { title: 'Environment Safety', subtitle: 'Batas kondisi lingkungan area kerja.', icon: Thermometer, fields: [['temperature_warning_threshold','Temperature Warning','°C'],['humidity_warning_threshold','Humidity Warning','%']] }
  ]

  // --- IOT DEVICES REGISTRY TAB ---
  const devicesQuery = useQuery({
    queryKey: ['devices'],
    queryFn: () => api<{ items: Device[] }>('/devices'),
    enabled: activeTab === 'devices'
  })
  const workersQuery = useQuery({
    queryKey: ['workers-list'],
    queryFn: () => api<{ items: Worker[] }>('/workers'),
    enabled: activeTab === 'devices'
  })
  const hazardsQuery = useQuery({
    queryKey: ['hazards-list'],
    queryFn: () => api<{ items: Hazard[] }>('/hazards'),
    enabled: activeTab === 'devices'
  })

  // Form states
  const [formDeviceId, setFormDeviceId] = useState('')
  const [formDeviceType, setFormDeviceType] = useState<DeviceType>('SMART_HELMET')
  const [targetId, setTargetId] = useState('')
  const [formAssignment, setFormAssignment] = useState('')
  const [successMsg, setSuccessMsg] = useState('')
  const [errorMsg, setErrorMsg] = useState('')
  const [isEditing, setIsEditing] = useState(false)

  useEffect(() => {
    if (isEditing) return // Skip resetting targetId while editing

    if (formDeviceType === 'SMART_HELMET' && workersQuery.data?.items?.length) {
      setTargetId(workersQuery.data.items[0].id)
    } else if (formDeviceType === 'HAZARD_NODE' && hazardsQuery.data?.items?.length) {
      setTargetId(hazardsQuery.data.items[0].id)
    } else {
      setTargetId('')
    }
  }, [formDeviceType, workersQuery.data, hazardsQuery.data, isEditing])

  const pairMutation = useMutation({
    mutationFn: (data: { device_id: string; device_type: string; target_id: string; assignment: string }) =>
      api<{ device: Device; message: string }>('/devices/pair', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: ['devices'] })
      setSuccessMsg(res.message || 'Device successfully paired!')
      setErrorMsg('')
      setFormDeviceId('')
      setFormAssignment('')
      setIsEditing(false)
      // Clear message after 3 seconds
      setTimeout(() => setSuccessMsg(''), 3000)
    },
    onError: (err: unknown) => {
      setErrorMsg(getErrorMessage(err, 'Failed to pair device'))
      setSuccessMsg('')
    }
  })

  const deleteMutation = useMutation({
    mutationFn: (deviceId: string) =>
      api<{ message: string }>('/devices/' + deviceId, {
        method: 'DELETE'
      }),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: ['devices'] })
      setSuccessMsg(res.message || 'Device deleted successfully.')
      setErrorMsg('')
      setTimeout(() => setSuccessMsg(''), 3000)
    },
    onError: (err: unknown) => {
      setErrorMsg(getErrorMessage(err, 'Failed to delete device'))
      setSuccessMsg('')
    }
  })

  const handlePairSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formDeviceId || !targetId) {
      setErrorMsg('Device ID dan target perangkat wajib diisi.')
      return
    }
    pairMutation.mutate({
      device_id: formDeviceId.trim(),
      device_type: formDeviceType,
      target_id: targetId,
      assignment: formAssignment.trim()
    })
  }

  const handleEditClick = (dev: Device) => {
    setIsEditing(true)
    setFormDeviceId(dev.id)
    setFormDeviceType(dev.type as DeviceType)
    setFormAssignment(dev.assignment)
    if (dev.type === 'SMART_HELMET') {
      const matched = workersQuery.data?.items.find((w) => w.name === dev.assignment)
      setTargetId(matched?.id || '')
    } else if (dev.type === 'HAZARD_NODE') {
      const matched = hazardsQuery.data?.items.find((h) => h.name === dev.assignment)
      setTargetId(matched?.id || '')
    } else {
      setTargetId(dev.assignment)
    }
    setErrorMsg('')
    setSuccessMsg('')
  }

  const handleDeleteClick = (devId: string) => {
    if (window.confirm(`Apakah Anda yakin ingin menghapus perangkat ${devId}?`)) {
      deleteMutation.mutate(devId)
    }
  }



  if (activeTab === 'system' && query.isLoading) return <LoadingState />
  if (activeTab === 'system' && query.isError) return <ErrorState retry={() => void query.refetch()} />

  return (
    <div className="stack-lg wide-page settings-page">
      <div className="settings-tabs">
        <button className={activeTab === 'system' ? 'active' : ''} onClick={() => setActiveTab('system')}>
          Safety Thresholds
        </button>
        <button className={activeTab === 'devices' ? 'active' : ''} onClick={() => setActiveTab('devices')}>
          IoT Device Registry
        </button>
      </div>

      {activeTab === 'system' ? (
        <div className="stack-lg">
          <div className="settings-warning">
            <AlertTriangle size={20} />
            <div>
              <strong>Safety-critical configuration</strong>
              <span>Perubahan threshold langsung memengaruhi klasifikasi proximity, near-miss, dan peringatan helm.</span>
            </div>
          </div>
          <div className="settings-grid">
            {sections.map(({ title, subtitle, icon: Icon, fields }) => (
              <section className="settings-card" key={title}>
                <div className="settings-head">
                  <Icon size={21} />
                  <div>
                    <h2>{title}</h2>
                    <p>{subtitle}</p>
                  </div>
                </div>
                <div className="settings-fields">
                  {fields.map(([key, label, unit]) => (
                    <label key={key}>
                      <span>{label}</span>
                      <div>
                        <input
                          type="number"
                          value={values[key] ?? ''}
                          onChange={(e) => update(key, e.target.value)}
                        />
                        <b>{unit}</b>
                      </div>
                    </label>
                  ))}
                </div>
              </section>
            ))}
            <section className="settings-card" style={{ border: '1px solid rgba(239, 68, 68, 0.2)' }}>
              <div className="settings-head">
                <AlertTriangle size={21} style={{ color: '#be323c' }} />
                <div>
                  <h2 style={{ color: '#be323c' }}>Data & Simulation Management</h2>
                  <p>Kembalikan data demo bawaan untuk worker, forklift, hazard, dan device.</p>
                </div>
              </div>
              <div className="settings-fields" style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
                <span style={{ fontSize: '13px', color: 'var(--muted)' }}>
                  Gunakan ini kalau daftar forklift/hazard kosong atau setelah mencoba skenario IoT.
                </span>
                <button
                  className="button danger reset-demo-button"
                  style={{ width: 'fit-content' }}
                  onClick={handleClearSimulationData}
                  disabled={clearMutation.isPending}
                >
                  <Trash2 size={16} />
                  {clearMutation.isPending ? 'Mereset...' : 'Reset Demo Data'}
                </button>
              </div>
            </section>
          </div>
          <div className="settings-save">
            <label>
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
              />
              <span>Saya memahami perubahan ini memengaruhi threshold keselamatan operasional.</span>
            </label>
            <button
              className="button primary"
              disabled={!confirmed || mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              <Save size={16} />
              {mutation.isPending ? 'Menyimpan...' : 'Save Configuration'}
            </button>
            {mutation.isSuccess && (
              <span className="success-message">
                <CheckCircle2 size={16} /> Pengaturan tersimpan.
              </span>
            )}
            {mutation.isError && <span className="error-message">{mutation.error.message}</span>}
          </div>
        </div>
      ) : (
        // --- IOT DEVICE REGISTRY LAYOUT ---
        <div className="device-registry-grid">
          {/* Registry List Table */}
          <div className="stack-md">
            {devicesQuery.isLoading ? (
              <LoadingState label="Memuat registry perangkat..." />
            ) : devicesQuery.isError ? (
              <ErrorState retry={() => void devicesQuery.refetch()} />
            ) : (
              <Panel
                title="Registered Devices"
                subtitle={`${devicesQuery.data?.items.length ?? 0} IoT nodes active in the field`}
                action={
                  <button className="button secondary" onClick={() => void devicesQuery.refetch()}>
                    <RefreshCw size={14} /> Refresh
                  </button>
                }
              >
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Device ID</th>
                        <th>Type</th>
                        <th>Linked Asset</th>
                        <th>Last Seen</th>
                        <th style={{ textAlign: 'right' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {devicesQuery.data?.items.map((dev) => (
                        <tr key={dev.id}>
                          <td className="mono" style={{ fontWeight: 700 }}>{dev.id}</td>
                          <td>
                            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--muted)' }}>
                              {dev.type.replaceAll('_', ' ')}
                            </span>
                          </td>
                          <td>
                            <strong>{dev.assignment || '-'}</strong>
                          </td>
                          <td>
                            <small>{formatDate(dev.last_seen)}</small>
                          </td>
                           <td style={{ textAlign: 'right' }}>
                            <div style={{ display: 'inline-flex', gap: '8px' }}>
                              <button
                                className="action-btn"
                                style={{ color: 'var(--blue)' }}
                                title="Edit Device"
                                onClick={() => handleEditClick(dev)}
                              >
                                <Edit2 size={15} />
                              </button>
                              <button
                                className="action-btn danger-btn"
                                style={{ color: '#ef4444' }}
                                title="Delete Device"
                                onClick={() => handleDeleteClick(dev.id)}
                              >
                                <Trash2 size={15} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>
            )}
          </div>

          {/* Pair/Register Form Panel */}
          <div className="device-form-panel">
            <h3>{isEditing ? 'Edit IoT Device' : 'Pair & Register IoT Device'}</h3>
            <p style={{ fontSize: '13px', color: 'var(--muted)', margin: '-10px 0 20px 0', lineHeight: 1.4 }}>
              {isEditing
                ? 'Perbarui hubungan device ID ke pekerja, mesin hazard, atau area sensor.'
                : 'Daftarkan node baru sebagai helm pekerja, beacon mesin hazard, atau sensor lingkungan area.'}
            </p>

            <form onSubmit={handlePairSubmit} className="device-form">
              <label>
                <span>Device ID (MAC/Serial)</span>
                <input
                  type="text"
                  placeholder="e.g. HELMET-W07, HAZARD-G02"
                  value={formDeviceId}
                  onChange={(e) => setFormDeviceId(e.target.value)}
                  disabled={isEditing}
                  required
                />
              </label>

              <label>
                <span>Device Type</span>
                <select
                  value={formDeviceType}
                  onChange={(e) => setFormDeviceType(e.target.value as DeviceType)}
                >
                  <option value="SMART_HELMET">Smart Helmet (Helmet)</option>
                  <option value="HAZARD_NODE">Hazard Beacon (Forklift/Machine)</option>
                  <option value="ENVIRONMENT_NODE">Environment Station (Sensor)</option>
                </select>
              </label>

              {formDeviceType === 'SMART_HELMET' && (
                <label>
                  <span>Assign to Worker</span>
                  <select value={targetId} onChange={(e) => setTargetId(e.target.value)} required>
                    {workersQuery.data?.items.map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.name} ({w.role})
                      </option>
                    ))}
                  </select>
                </label>
              )}

              {formDeviceType === 'HAZARD_NODE' && (
                <label>
                  <span>Link to Forklift / Hazard Machine (ID)</span>
                  <input
                    type="text"
                    placeholder="e.g. F01, Forklift-Gudang"
                    value={targetId}
                    onChange={(e) => setTargetId(e.target.value)}
                    required
                  />
                  <span style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '4px', display: 'block' }}>
                    * Jika ID alat belum ada, sistem akan otomatis mendaftarkannya sebagai Hazard baru.
                  </span>
                </label>
              )}

              {formDeviceType === 'ENVIRONMENT_NODE' && (
                <label>
                  <span>Target Area / Code</span>
                  <input
                    type="text"
                    placeholder="e.g. Gudang Utama, Produksi B"
                    value={targetId}
                    onChange={(e) => setTargetId(e.target.value)}
                    required
                  />
                </label>
              )}

              <label>
                <span>Assignment Label / Note (Optional)</span>
                <input
                  type="text"
                  placeholder="e.g. Helmet Andy, Forklift Alpha"
                  value={formAssignment}
                  onChange={(e) => setFormAssignment(e.target.value)}
                />
              </label>

              {successMsg && (
                <div style={{ color: '#059669', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
                  <CheckCircle2 size={16} /> {successMsg}
                </div>
              )}

              {errorMsg && (
                <div style={{ color: '#ef4444', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
                  <ShieldAlert size={16} /> {errorMsg}
                </div>
              )}

              <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                {isEditing && (
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() => {
                      setIsEditing(false)
                      setFormDeviceId('')
                      setFormAssignment('')
                      setErrorMsg('')
                    }}
                    style={{ flex: 1 }}
                  >
                    Batal
                  </button>
                )}
                <button
                  type="submit"
                  className="button primary"
                  disabled={pairMutation.isPending}
                  style={{ flex: 2 }}
                >
                  <Plus size={16} />{' '}
                  {pairMutation.isPending
                    ? 'Processing...'
                    : isEditing
                    ? 'Simpan Perubahan'
                    : 'Register & Pair'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
