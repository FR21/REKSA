import { useEffect, useMemo, useState, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  CheckCircle2,
  Radio,
  Save,
  Thermometer,
  ShieldAlert,
  Plus,
  RefreshCw,
  Edit2,
  Trash2,
  Copy,
  Check,
  ChevronUp,
  Cpu,
  Filter,
  MoreVertical,
  X,
  SlidersHorizontal,
  HardHat,
  Truck,
  Factory,
} from 'lucide-react'
import { api, getErrorMessage } from '../services/api'
import { ErrorState, LoadingState } from '../components/common/States'
import type { Device, Worker, Hazard } from '../types'
import { Panel } from '../components/common/Panel'
import { Pagination } from '../components/common/Pagination'
import { formatDate } from '../lib/utils'
import { useTranslation } from '../i18n'
import { useCatalogOptions } from '../hooks/useCatalogOptions'

type Settings = Record<string, number>
type DeviceType = 'SMART_HELMET' | 'HAZARD_MOBILE' | 'HAZARD_STATIONARY' | 'HAZARD_NODE'

const HAZARD_TYPE_CONFIG: Record<string, { code: string; label: string; category: 'MOBILE' | 'STATIONARY' }> = {
  FORKLIFT: { code: 'FLK', label: 'Forklift (Counterbalance/Reach)', category: 'MOBILE' },
  CONTAINER_CRANE: { code: 'CNT', label: 'Reach Stacker / Container Crane', category: 'MOBILE' },
  AGV: { code: 'AGV', label: 'Automated Guided Vehicle (AGV)', category: 'MOBILE' },
  TRUCK: { code: 'TRK', label: 'Heavy Haul Truck / Trailer', category: 'MOBILE' },
  CRANE: { code: 'CRN', label: 'Mobile / Overhead Jib Crane', category: 'MOBILE' },
  LASER: { code: 'LSR', label: 'Fiber / CO2 Laser Cutter', category: 'STATIONARY' },
  GRINDING: { code: 'GRD', label: 'Bench / Surface Grinder', category: 'STATIONARY' },
  PRESS: { code: 'PRS', label: 'Stamping / Hydraulic Press', category: 'STATIONARY' },
  CNC: { code: 'CNC', label: 'CNC Milling / Lathe Center', category: 'STATIONARY' },
  ROBOT: { code: 'ROB', label: 'Robotic Arm Cell', category: 'STATIONARY' },
  MACHINERY: { code: 'MCN', label: 'Heavy Production Machinery', category: 'STATIONARY' },
}


export default function SettingsPage() {
  const queryClient = useQueryClient()
  const { t, language } = useTranslation()
  const [activeTab, setActiveTab] = useState<'system' | 'devices'>('system')

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

  const update = (key: string, val: string) => {
    const num = Number(val)
    setValues((prev) => ({ ...prev, [key]: Number.isNaN(num) ? prev[key] : num }))
  }

  const sections = [
    {
      title: t.settings.sectionGasTitle,
      subtitle: t.settings.sectionGasDesc,
      icon: Thermometer,
      fields: [
        ['heat_warning_c', t.settings.fieldHeatWarning, '°C'],
        ['heat_danger_c', t.settings.fieldHeatDanger, '°C'],
        ['mq135_normal_max', t.settings.fieldMqNormal, 'ADC'],
        ['mq135_moderate_max', t.settings.fieldMqModerate, 'ADC'],
        ['mq135_poor_max', t.settings.fieldMqPoor, 'ADC']
      ]
    },
    {
      title: t.settings.sectionImpactTitle,
      subtitle: t.settings.sectionImpactDesc,
      icon: Radio,
      fields: [
        ['impact_g_warning', t.settings.fieldImpactWarning, 'g'],
        ['impact_g_critical', t.settings.fieldImpactCritical, 'g'],
        ['fall_freefall_g', t.settings.fieldFallFreefall, 'g']
      ]
    }
  ]

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

  const [formDeviceId, setFormDeviceId] = useState('')
  const [formDeviceType, setFormDeviceType] = useState<DeviceType>('SMART_HELMET')
  const [targetId, setTargetId] = useState('')
  const [formAssignment, setFormAssignment] = useState('')
  const [successMsg, setSuccessMsg] = useState('')
  const [errorMsg, setErrorMsg] = useState('')
  const [isEditing, setIsEditing] = useState(false)
  const [isPairModalOpen, setIsPairModalOpen] = useState(false)
  const [devicePage, setDevicePage] = useState(1)
  const [deviceTypeFilter, setDeviceTypeFilter] = useState('ALL')
  const devicePageSize = 6

  const rawDevices = useMemo(() => devicesQuery.data?.items ?? [], [devicesQuery.data])

  const filteredDevices = useMemo(() => {
    if (deviceTypeFilter === 'ALL') return rawDevices
    return rawDevices.filter((d) => d.type === deviceTypeFilter)
  }, [rawDevices, deviceTypeFilter])

  const totalDevicePages = Math.ceil(filteredDevices.length / devicePageSize) || 1
  const paginatedDevices = useMemo(() => {
    const start = (devicePage - 1) * devicePageSize
    return filteredDevices.slice(start, start + devicePageSize)
  }, [filteredDevices, devicePage, devicePageSize])

  useEffect(() => {
    if (devicePage > totalDevicePages) {
      setDevicePage(1)
    }
  }, [totalDevicePages, devicePage])

  // State untuk Registrasi Hazard Baru
  const [showAssetCreator, setShowAssetCreator] = useState(false)
  const [newHazardType, setNewHazardType] = useState('FORKLIFT')
  const [newHazardNum, setNewHazardNum] = useState('04')
  const [newHazardName, setNewHazardName] = useState('')
  const [newHazardArea, setNewHazardArea] = useState('Gudang Utama')
  const [copiedBeacon, setCopiedBeacon] = useState(false)
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null)
  const menuRef = useRef<HTMLDivElement | null>(null)

  const { areas, addArea } = useCatalogOptions(
    workersQuery.data?.items || [],
    hazardsQuery.data?.items || []
  )
  const [isAddingHazardArea, setIsAddingHazardArea] = useState(false)
  const [newHazardAreaInput, setNewHazardAreaInput] = useState('')
  const [showManualConfig, setShowManualConfig] = useState(false)

  // Close 3-dot menu on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setActiveMenuId(null)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Nilai terhitung dari form creator
  const targetCategory = formDeviceType === 'HAZARD_STATIONARY' ? 'STATIONARY' : 'MOBILE'
  const activeTypeCfg = HAZARD_TYPE_CONFIG[newHazardType] || { code: 'FLK', label: 'Forklift', category: targetCategory }
  const catPrefix = activeTypeCfg.category === 'MOBILE' ? 'M' : 'S'
  const unitNum = (newHazardNum.padStart(2, '0')).slice(-2)
  const computedAssetId = `${catPrefix}-${activeTypeCfg.code}-${unitNum}`
  const computedBeaconName = `RK_${catPrefix}_${activeTypeCfg.code}${unitNum}`

  const isDuplicateHazardId = useMemo(() => {
    return hazardsQuery.data?.items.some((h) => h.id.toUpperCase() === computedAssetId.toUpperCase()) ?? false
  }, [hazardsQuery.data?.items, computedAssetId])

  const duplicateHazard = isDuplicateHazardId
    ? hazardsQuery.data?.items.find((h) => h.id.toUpperCase() === computedAssetId.toUpperCase())
    : null

  // Otomatis sarankan nomor unit berikutnya saat memilih tipe mesin agar ID selalu unik
  useEffect(() => {
    const prefix = `${catPrefix}-${activeTypeCfg.code}-`
    const matching = hazardsQuery.data?.items.filter((h) => h.id.toUpperCase().startsWith(prefix.toUpperCase())) ?? []
    const nums = matching.map((h) => {
      const numPart = h.id.replace(new RegExp(`^${prefix}`, 'i'), '')
      const n = parseInt(numPart, 10)
      return isNaN(n) ? 0 : n
    })
    const nextNum = nums.length > 0 ? Math.max(...nums) + 1 : 1
    setNewHazardNum(String(nextNum).padStart(2, '0'))
  }, [newHazardType, catPrefix, activeTypeCfg.code, hazardsQuery.data?.items])

  // Hazard yang saat ini terpilih
  const selectedHazard = hazardsQuery.data?.items.find((h) => h.id === targetId || h.alias === targetId)

  // Otomatis sinkronisasi target saat mengganti Device Type
  useEffect(() => {
    if (isEditing) return

    if (formDeviceType === 'SMART_HELMET') {
      const firstWorker = workersQuery.data?.items?.[0]
      if (firstWorker) {
        setTargetId(firstWorker.id)
        setFormDeviceId(`DEV-HLM-${firstWorker.id}`)
        setFormAssignment(firstWorker.name)
      }
    } else if (formDeviceType === 'HAZARD_MOBILE') {
      const mobiles = hazardsQuery.data?.items?.filter((h) => h.category === 'MOBILE')
      if (mobiles && mobiles.length > 0) {
        setTargetId(mobiles[0].id)
        setFormDeviceId(`DEV-BCN-${mobiles[0].id}`)
        setFormAssignment(mobiles[0].name)
      } else {
        setTargetId('')
      }
      setNewHazardType('FORKLIFT')
    } else if (formDeviceType === 'HAZARD_STATIONARY') {
      const stationaries = hazardsQuery.data?.items?.filter((h) => h.category === 'STATIONARY')
      if (stationaries && stationaries.length > 0) {
        setTargetId(stationaries[0].id)
        setFormDeviceId(`DEV-BCN-${stationaries[0].id}`)
        setFormAssignment(stationaries[0].name)
      } else {
        setTargetId('')
      }
      setNewHazardType('LASER')
    } else {
      setTargetId('')
    }
  }, [formDeviceType, workersQuery.data, hazardsQuery.data, isEditing])

  const handleOpenPairModal = () => {
    setIsEditing(false)
    setShowAssetCreator(false)
    setShowManualConfig(false)
    setErrorMsg('')
    setSuccessMsg('')
    if (formDeviceType === 'SMART_HELMET') {
      const firstWorker = workersQuery.data?.items?.[0]
      if (firstWorker) {
        setTargetId(firstWorker.id)
        setFormDeviceId(`DEV-HLM-${firstWorker.id}`)
        setFormAssignment(firstWorker.name)
      }
    } else if (formDeviceType === 'HAZARD_MOBILE') {
      const mobiles = hazardsQuery.data?.items?.filter((h) => h.category === 'MOBILE')
      if (mobiles && mobiles[0]) {
        setTargetId(mobiles[0].id)
        setFormDeviceId(`DEV-BCN-${mobiles[0].id}`)
        setFormAssignment(mobiles[0].name)
      }
    } else if (formDeviceType === 'HAZARD_STATIONARY') {
      const stats = hazardsQuery.data?.items?.filter((h) => h.category === 'STATIONARY')
      if (stats && stats[0]) {
        setTargetId(stats[0].id)
        setFormDeviceId(`DEV-BCN-${stats[0].id}`)
        setFormAssignment(stats[0].name)
      }
    }
    setIsPairModalOpen(true)
  }

  const handleClosePairModal = () => {
    setIsPairModalOpen(false)
    setIsEditing(false)
    setShowAssetCreator(false)
    setShowManualConfig(false)
    setErrorMsg('')
  }

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isPairModalOpen) {
        handleClosePairModal()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isPairModalOpen])

  const pairMutation = useMutation({
    mutationFn: (data: { device_id: string; device_type: string; target_id: string; assignment: string }) =>
      api<{ device: Device; message: string }>('/devices/pair', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: ['devices'] })
      setSuccessMsg(res.message || 'Perangkat berhasil dipairing!')
      setErrorMsg('')
      setFormDeviceId('')
      setFormAssignment('')
      setIsEditing(false)
      setIsPairModalOpen(false)
      setTimeout(() => setSuccessMsg(''), 4000)
    },
    onError: (err: unknown) => {
      setErrorMsg(getErrorMessage(err, 'Gagal mempairing perangkat'))
      setSuccessMsg('')
    }
  })

  const createHazardMutation = useMutation({
    mutationFn: (data: { id: string; name: string; type: string; category: string; area: string; beacon_name: string }) =>
      api<{ hazard: Hazard; message: string }>('/hazards', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: ['hazards-list'] })
      void queryClient.invalidateQueries({ queryKey: ['devices'] })
      setTargetId(res.hazard.id)
      setFormDeviceId(`DEV-BCN-${res.hazard.id}`)
      setFormAssignment(res.hazard.name)
      setShowAssetCreator(false)
      setSuccessMsg(`Aset ${res.hazard.id} (${res.hazard.name}) berhasil didaftarkan dan siap dipairing!`)
      setTimeout(() => setSuccessMsg(''), 4000)
    },
    onError: (err: unknown) => {
      setErrorMsg(getErrorMessage(err, 'Gagal mendaftarkan hazard baru'))
    }
  })

  const deleteMutation = useMutation({
    mutationFn: (deviceId: string) =>
      api<{ message: string }>('/devices/' + deviceId, {
        method: 'DELETE'
      }),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: ['devices'] })
      setSuccessMsg(res.message || 'Perangkat berhasil dihapus.')
      setErrorMsg('')
      setTimeout(() => setSuccessMsg(''), 3000)
    },
    onError: (err: unknown) => {
      setErrorMsg(getErrorMessage(err, 'Gagal menghapus perangkat'))
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

  const handleCreateHazardSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newHazardName.trim()) {
      setErrorMsg('Nama hazard wajib diisi (misal: Forklift Delta).')
      return
    }
    createHazardMutation.mutate({
      id: computedAssetId,
      name: newHazardName.trim(),
      type: newHazardType,
      category: activeTypeCfg.category,
      area: newHazardArea,
      beacon_name: computedBeaconName,
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
    } else if (dev.type === 'HAZARD_NODE' || dev.type === 'HAZARD_MOBILE' || dev.type === 'HAZARD_STATIONARY') {
      const matched = hazardsQuery.data?.items.find((h) => h.name === dev.assignment || h.id === dev.id.replace('DEV-BCN-', '').replace('HAZARD-', ''))
      setTargetId(matched?.id || '')
    } else {
      setTargetId(dev.assignment)
    }
    setErrorMsg('')
    setSuccessMsg('')
    setIsPairModalOpen(true)
  }

  const handleDeleteClick = (devId: string) => {
    if (window.confirm(t.settings.confirmDeleteDevice(devId))) {
      deleteMutation.mutate(devId)
    }
  }

  const copyToClipboard = (text: string) => {
    void navigator.clipboard.writeText(text)
    setCopiedBeacon(true)
    setTimeout(() => setCopiedBeacon(false), 2000)
  }

  if (activeTab === 'system' && query.isLoading) return <LoadingState />
  if (activeTab === 'system' && query.isError) return <ErrorState retry={() => void query.refetch()} />

  const mobileHazards = hazardsQuery.data?.items.filter((h) => h.category === 'MOBILE') ?? []
  const stationaryHazards = hazardsQuery.data?.items.filter((h) => h.category === 'STATIONARY') ?? []

  return (
    <div className="stack-lg wide-page settings-page">
      <div className="settings-tabs">
        <button className={activeTab === 'system' ? 'active' : ''} onClick={() => setActiveTab('system')}>
          {t.settings.tabProximity}
        </button>
        <button className={activeTab === 'devices' ? 'active' : ''} onClick={() => setActiveTab('devices')}>
          {t.settings.tabRegistry}
        </button>
      </div>

      {activeTab === 'system' ? (
        <div className="stack-lg">
          <div className="settings-warning">
            <AlertTriangle size={20} />
            <div>
              <strong>{t.settings.warningBannerTitle}</strong>
              <span>{t.settings.warningBannerDesc}</span>
            </div>
          </div>

          <div className="settings-grid">
            {sections.map(({ title, subtitle, icon: Icon, fields }) => (
              <section className="settings-card" key={title}>
                <div className="settings-head">
                  <Icon size={20} />
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

            {/* DUAL-PROFILE CALIBRATED RSSI CARD */}
            <section className="settings-card" style={{ border: '1px solid rgba(239, 68, 68, 0.2)' }}>
              <div className="settings-head" style={{ color: '#ef4444' }}>
                <Radio size={20} />
                <div>
                  <h2>{t.settings.profileMobileTitle}</h2>
                  <p>{t.settings.profileMobileDesc}</p>
                </div>
              </div>
              <div className="settings-fields">
                <label>
                  <span>{t.settings.criticalDistance} (~3.5m)</span>
                  <div>
                    <input
                      type="number"
                      value={values['mobile_critical_rssi'] ?? -70}
                      onChange={(e) => update('mobile_critical_rssi', e.target.value)}
                    />
                    <b>dBm</b>
                  </div>
                </label>
                <label>
                  <span>{t.settings.highWarning} (~6.0m)</span>
                  <div>
                    <input
                      type="number"
                      value={values['mobile_high_rssi'] ?? -78}
                      onChange={(e) => update('mobile_high_rssi', e.target.value)}
                    />
                    <b>dBm</b>
                  </div>
                </label>
                <label>
                  <span>{t.settings.moderatePerimeter} (~10.0m)</span>
                  <div>
                    <input
                      type="number"
                      value={values['mobile_moderate_rssi'] ?? -86}
                      onChange={(e) => update('mobile_moderate_rssi', e.target.value)}
                    />
                    <b>dBm</b>
                  </div>
                </label>
              </div>
            </section>

            <section className="settings-card" style={{ border: '1px solid rgba(59, 130, 246, 0.2)' }}>
              <div className="settings-head" style={{ color: '#3b82f6' }}>
                <Radio size={20} />
                <div>
                  <h2>{t.settings.profileStationaryTitle}</h2>
                  <p>{t.settings.profileStationaryDesc}</p>
                </div>
              </div>
              <div className="settings-fields">
                <label>
                  <span>{t.settings.criticalDistance} (~1.2m)</span>
                  <div>
                    <input
                      type="number"
                      value={values['stationary_critical_rssi'] ?? -65}
                      onChange={(e) => update('stationary_critical_rssi', e.target.value)}
                    />
                    <b>dBm</b>
                  </div>
                </label>
                <label>
                  <span>{t.settings.highWarning} (~2.5m)</span>
                  <div>
                    <input
                      type="number"
                      value={values['stationary_high_rssi'] ?? -74}
                      onChange={(e) => update('stationary_high_rssi', e.target.value)}
                    />
                    <b>dBm</b>
                  </div>
                </label>
                <label>
                  <span>{t.settings.moderatePerimeter} (~4.0m)</span>
                  <div>
                    <input
                      type="number"
                      value={values['stationary_moderate_rssi'] ?? -82}
                      onChange={(e) => update('stationary_moderate_rssi', e.target.value)}
                    />
                    <b>dBm</b>
                  </div>
                </label>
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
              <span>{t.settings.confirmCheckbox}</span>
            </label>
            <button
              className="button primary"
              disabled={!confirmed || mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              <Save size={16} /> {mutation.isPending ? t.settings.btnSavingThreshold : t.settings.btnSaveThreshold}
            </button>
          </div>
        </div>
      ) : (
        <div className="device-registry-full">
          <div className="stack-md">
            {successMsg && !isPairModalOpen && (
              <div style={{ color: '#059669', background: '#ecfdf5', border: '1px solid #a7f3d0', padding: '10px 16px', borderRadius: '8px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600 }}>
                <CheckCircle2 size={16} /> {successMsg}
              </div>
            )}

            {devicesQuery.isLoading ? (
              <LoadingState />
            ) : devicesQuery.isError ? (
              <ErrorState retry={() => void devicesQuery.refetch()} />
            ) : (
              <Panel
                title={t.settings.panelRegistryTitle}
                subtitle={t.settings.panelRegistrySubtitle(filteredDevices.length, rawDevices.length)}
                action={
                  <div className="panel-action-group">
                    <div className="filter-control">
                      <Filter size={16} />
                      <select
                        value={deviceTypeFilter}
                        onChange={(e) => {
                          setDeviceTypeFilter(e.target.value)
                          setDevicePage(1)
                        }}
                      >
                        <option value="ALL">{t.settings.filterAllTypes}</option>
                        <option value="SMART_HELMET">{t.settings.filterHelmet}</option>
                        <option value="HAZARD_MOBILE">{t.settings.filterHazardMobile}</option>
                        <option value="HAZARD_STATIONARY">{t.settings.filterHazardStationary}</option>
                      </select>
                    </div>

                    <button
                      className="button secondary"
                      disabled={devicesQuery.isFetching}
                      onClick={() => void devicesQuery.refetch()}
                      title={t.settings.refreshTooltip}
                      style={{ whiteSpace: 'nowrap' }}
                    >
                      <RefreshCw size={16} className={devicesQuery.isFetching ? 'spin' : ''} />
                      {devicesQuery.isFetching ? t.settings.btnRefreshing : t.settings.btnRefresh}
                    </button>

                    <button
                      type="button"
                      className="button primary"
                      onClick={handleOpenPairModal}
                      style={{ whiteSpace: 'nowrap' }}
                    >
                      <Plus size={16} />
                      {t.settings.btnOpenPairModal}
                    </button>
                  </div>
                }
              >
                {filteredDevices.length === 0 ? (
                  <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--muted)', fontSize: '14px' }}>
                    {t.settings.emptyDevices}
                  </div>
                ) : (
                  <>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>{t.settings.colDeviceId}</th>
                            <th>{t.settings.colType}</th>
                            <th>{t.settings.colLinkedTarget}</th>
                            <th>{t.settings.colStatus}</th>
                            <th>{t.settings.colLastSeen}</th>
                            <th style={{ textAlign: 'right' }}>{t.settings.colAction}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {paginatedDevices.map((dev, index) => (
                            <tr key={dev.id}>
                              <td>
                                <strong className="mono" style={{ fontSize: '12px', color: '#1e293b' }}>{dev.id}</strong>
                                <small style={{ display: 'block', color: 'var(--muted)', fontSize: '12px' }}>
                                  {dev.topic}
                                </small>
                              </td>
                              <td>
                                <span style={{
                                  fontSize: '12px',
                                  fontWeight: 700,
                                  padding: '2px 8px',
                                  borderRadius: '4px',
                                  textTransform: 'uppercase',
                                  background: dev.type.includes('MOBILE') ? 'rgba(239, 68, 68, 0.12)' : dev.type.includes('STATIONARY') ? 'rgba(59, 130, 246, 0.12)' : 'rgba(100, 116, 139, 0.12)',
                                  color: dev.type.includes('MOBILE') ? '#dc2626' : dev.type.includes('STATIONARY') ? '#2563eb' : '#475569'
                                }}>
                                  {dev.type.replaceAll('_', ' ')}
                                </span>
                              </td>
                              <td>
                                <strong>{dev.assignment || '-'}</strong>
                              </td>
                              <td>
                                <span className={`online-label ${!dev.online ? 'offline' : ''}`} style={{ fontSize: '12px' }}>
                                  <i /> {dev.online ? t.common.online : t.common.offline}
                                </span>
                              </td>
                              <td>
                                <small>{formatDate(dev.last_seen, language)}</small>
                              </td>
                              <td
                                style={{ textAlign: 'right' }}
                                onClick={(e) => e.stopPropagation()}
                              >
                                <div
                                  className="action-menu-container"
                                  ref={activeMenuId === dev.id ? menuRef : null}
                                >
                                  <button
                                    className="action-btn"
                                    title={t.workers.actionMenuTooltip}
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      setActiveMenuId(activeMenuId === dev.id ? null : dev.id)
                                    }}
                                  >
                                    <MoreVertical size={16} />
                                  </button>

                                  {activeMenuId === dev.id && (
                                    <div className={`action-menu-dropdown ${index >= paginatedDevices.length - 2 && paginatedDevices.length > 2 ? 'dropdown-up' : ''}`}>
                                      <button
                                        className="action-menu-item"
                                        onClick={(e) => {
                                          e.stopPropagation()
                                          setActiveMenuId(null)
                                          handleEditClick(dev)
                                        }}
                                      >
                                        <Edit2 size={14} style={{ color: 'var(--blue)' }} />
                                        <span>{t.common.edit}</span>
                                      </button>
                                      <button
                                        className="action-menu-item danger"
                                        onClick={(e) => {
                                          e.stopPropagation()
                                          setActiveMenuId(null)
                                          handleDeleteClick(dev.id)
                                        }}
                                      >
                                        <Trash2 size={14} />
                                        <span>{t.common.delete}</span>
                                      </button>
                                    </div>
                                  )}
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <Pagination
                      currentPage={devicePage}
                      totalPages={totalDevicePages}
                      totalItems={filteredDevices.length}
                      pageSize={devicePageSize}
                      onPageChange={setDevicePage}
                      itemName={t.settings.itemUnit}
                    />
                  </>
                )}
              </Panel>
            )}
          </div>

        </div>
      )}

      {/* MODAL PAIR & REGISTER DEVICE */}
      {isPairModalOpen && (
        <div
          className="modal-backdrop"
          onClick={handleClosePairModal}
          role="dialog"
          aria-modal="true"
          aria-labelledby="pair-modal-title"
        >
          <div
            className="modal-dialog modal-pair-device"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <h3 id="pair-modal-title">{isEditing ? t.settings.formEditTitle : t.settings.formRegisterTitle}</h3>
                <p style={{ fontSize: '12px', color: 'var(--muted)', margin: '4px 0 0 0' }}>
                  {isEditing ? t.settings.formEditDesc : t.settings.formRegisterDesc}
                </p>
              </div>
              <button
                type="button"
                onClick={handleClosePairModal}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--muted)', padding: '4px' }}
                aria-label={t.common.cancel}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handlePairSubmit} style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
              <div className="modal-body">
                {/* 1. SELEKTOR TIPE PERANGKAT BERBASIS TILE KARTU */}
                <div className="device-type-selector-grid">
                  <button
                    type="button"
                    className={`device-type-tile ${formDeviceType === 'SMART_HELMET' ? 'active' : ''}`}
                    onClick={() => {
                      setFormDeviceType('SMART_HELMET')
                      setShowAssetCreator(false)
                    }}
                    disabled={isEditing}
                  >
                    <div className="tile-icon"><HardHat size={22} /></div>
                    <div className="tile-content">
                      <span className="tile-title">{t.settings.tileHelmetTitle}</span>
                      <span className="tile-desc">{t.settings.tileHelmetDesc}</span>
                    </div>
                  </button>
                  <button
                    type="button"
                    className={`device-type-tile ${formDeviceType === 'HAZARD_MOBILE' ? 'active' : ''}`}
                    onClick={() => {
                      setFormDeviceType('HAZARD_MOBILE')
                      setShowAssetCreator(false)
                    }}
                    disabled={isEditing}
                  >
                    <div className="tile-icon"><Truck size={22} /></div>
                    <div className="tile-content">
                      <span className="tile-title">{t.settings.tileMobileTitle}</span>
                      <span className="tile-desc">{t.settings.tileMobileDesc}</span>
                    </div>
                  </button>
                  <button
                    type="button"
                    className={`device-type-tile ${formDeviceType === 'HAZARD_STATIONARY' ? 'active' : ''}`}
                    onClick={() => {
                      setFormDeviceType('HAZARD_STATIONARY')
                      setShowAssetCreator(false)
                    }}
                    disabled={isEditing}
                  >
                    <div className="tile-icon"><Factory size={22} /></div>
                    <div className="tile-content">
                      <span className="tile-title">{t.settings.tileStationaryTitle}</span>
                      <span className="tile-desc">{t.settings.tileStationaryDesc}</span>
                    </div>
                  </button>
                </div>

                {/* 2. TARGET PENUGASAN (WORKER / HAZARD / CREATOR) */}
                <div className="target-selector-card">
                  {formDeviceType === 'SMART_HELMET' && (
                    <label>
                      <span style={{ fontSize: '13px', fontWeight: 600, color: '#334155' }}>
                        {t.settings.labelSelectWorker}
                      </span>
                      <select
                        value={targetId}
                        onChange={(e) => {
                          const wId = e.target.value
                          setTargetId(wId)
                          const w = workersQuery.data?.items.find((x) => x.id === wId)
                          if (w) {
                            setFormDeviceId(`DEV-HLM-${w.id}`)
                            setFormAssignment(w.name)
                          }
                        }}
                        required
                      >
                        {workersQuery.data?.items.map((w) => (
                          <option key={w.id} value={w.id}>
                            {w.id} — {w.name} ({w.role} · {w.area})
                          </option>
                        ))}
                      </select>
                    </label>
                  )}

                  {/* SELECTOR MOBILE HAZARD */}
                  {(formDeviceType === 'HAZARD_MOBILE' || formDeviceType === 'HAZARD_NODE') && (
                    <div>
                      <label>
                        <div className="label-row">
                          <span style={{ fontSize: '13px', fontWeight: 600, color: '#334155' }}>{t.settings.labelSelectMobile}</span>
                          <button
                            type="button"
                            onClick={() => setShowAssetCreator(!showAssetCreator)}
                            style={{ background: 'none', border: 'none', color: '#2563eb', fontSize: '12px', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', margin: 0, padding: 0 }}
                          >
                            {showAssetCreator ? <ChevronUp size={16} /> : <Plus size={16} />} {showAssetCreator ? t.settings.btnCloseCreator : t.settings.btnOpenCreator}
                          </button>
                        </div>
                        <select
                          value={targetId}
                          onChange={(e) => {
                            const hId = e.target.value
                            setTargetId(hId)
                            const hz = hazardsQuery.data?.items.find((h) => h.id === hId)
                            if (hz) {
                              setFormDeviceId(`DEV-BCN-${hz.id}`)
                              setFormAssignment(hz.name)
                            }
                          }}
                          required
                        >
                          {mobileHazards.map((h) => (
                            <option key={h.id} value={h.id}>
                              {h.id} — {h.name} ({h.area})
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                  )}

                  {/* SELECTOR STATIONARY HAZARD */}
                  {formDeviceType === 'HAZARD_STATIONARY' && (
                    <div>
                      <label>
                        <div className="label-row">
                          <span style={{ fontSize: '13px', fontWeight: 600, color: '#334155' }}>{t.settings.labelSelectStationary}</span>
                          <button
                            type="button"
                            onClick={() => setShowAssetCreator(!showAssetCreator)}
                            style={{ background: 'none', border: 'none', color: '#2563eb', fontSize: '12px', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', margin: 0, padding: 0 }}
                          >
                            {showAssetCreator ? <ChevronUp size={16} /> : <Plus size={16} />} {showAssetCreator ? t.settings.btnCloseCreator : t.settings.btnOpenStationaryCreator}
                          </button>
                        </div>
                        <select
                          value={targetId}
                          onChange={(e) => {
                            const hId = e.target.value
                            setTargetId(hId)
                            const hz = hazardsQuery.data?.items.find((h) => h.id === hId)
                            if (hz) {
                              setFormDeviceId(`DEV-BCN-${hz.id}`)
                              setFormAssignment(hz.name)
                            }
                          }}
                          required
                        >
                          {stationaryHazards.map((h) => (
                            <option key={h.id} value={h.id}>
                              {h.id} — {h.name} ({h.area})
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                  )}

                  {/* STRUCTURED ASSET CREATOR SUB-FORM */}
                  {showAssetCreator && (formDeviceType === 'HAZARD_MOBILE' || formDeviceType === 'HAZARD_STATIONARY') && (
                    <div className="asset-creator-box">
                      <div className="asset-creator-title" style={{ display: 'flex', alignItems: 'center', color: '#0f172a', fontWeight: 700, fontSize: '13px' }}>
                        <span>{t.settings.creatorTitle(targetCategory)}</span>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 96px', gap: '8px', width: '100%', boxSizing: 'border-box' }}>
                        <label style={{ minWidth: 0, width: '100%' }}>
                          <span style={{ fontSize: '13px', fontWeight: 600, color: '#334155' }}>{t.settings.creatorMachineType}</span>
                          <select
                            value={newHazardType}
                            onChange={(e) => setNewHazardType(e.target.value)}
                            style={{ height: '38px', fontSize: '13px', width: '100%', minWidth: 0, boxSizing: 'border-box' }}
                          >
                            {Object.entries(HAZARD_TYPE_CONFIG)
                              .filter(([, cfg]) => cfg.category === targetCategory)
                              .map(([key, cfg]) => (
                                <option key={key} value={key}>
                                  {cfg.label} [{cfg.code}]
                                </option>
                              ))}
                          </select>
                        </label>

                        <label style={{ minWidth: 0, width: '100%' }}>
                          <span style={{ fontSize: '13px', fontWeight: 600, color: '#334155' }}>{t.settings.creatorUnitNum}</span>
                          <input
                            type="text"
                            maxLength={2}
                            value={newHazardNum}
                            onChange={(e) => setNewHazardNum(e.target.value.replace(/\D/g, ''))}
                            placeholder="01"
                            style={{ height: '38px', fontSize: '13px', fontFamily: 'monospace', width: '100%', minWidth: 0, boxSizing: 'border-box' }}
                          />
                        </label>
                      </div>

                      <label>
                        <span style={{ fontSize: '13px', fontWeight: 600, color: '#334155' }}>{t.settings.creatorDescriptiveName}</span>
                        <input
                          type="text"
                          placeholder="e.g. Forklift Alpha"
                          value={newHazardName}
                          onChange={(e) => setNewHazardName(e.target.value)}
                          style={{ height: '38px', fontSize: '13px', width: '100%', boxSizing: 'border-box' }}
                        />
                      </label>

                      <label>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: '13px', fontWeight: 600, color: '#334155' }}>{t.settings.creatorLocationArea}</span>
                          <button
                            type="button"
                            onClick={() => {
                              setIsAddingHazardArea(!isAddingHazardArea)
                              setNewHazardAreaInput('')
                            }}
                            style={{ background: 'none', border: 'none', color: '#2563eb', fontSize: '12px', fontWeight: 600, cursor: 'pointer', padding: 0 }}
                          >
                            {isAddingHazardArea ? t.common.cancel : `+ ${t.settings.addNewArea}`}
                          </button>
                        </div>

                        {isAddingHazardArea ? (
                          <div style={{ display: 'flex', gap: '6px', marginTop: '4px' }}>
                            <input
                              type="text"
                              value={newHazardAreaInput}
                              onChange={(e) => setNewHazardAreaInput(e.target.value)}
                              placeholder={t.settings.areaPlaceholder}
                              style={{ height: '38px', fontSize: '13px', flex: 1 }}
                            />
                            <button
                              type="button"
                              className="button primary"
                              style={{ fontSize: '12px', padding: '0 12px', height: '38px' }}
                              disabled={!newHazardAreaInput.trim()}
                              onClick={() => {
                                if (newHazardAreaInput.trim()) {
                                  addArea(newHazardAreaInput.trim())
                                  setNewHazardArea(newHazardAreaInput.trim())
                                  setIsAddingHazardArea(false)
                                  setNewHazardAreaInput('')
                                }
                              }}
                            >
                              {t.settings.btnSaveAndUse}
                            </button>
                          </div>
                        ) : (
                          <select
                            value={newHazardArea}
                            onChange={(e) => setNewHazardArea(e.target.value)}
                            style={{ height: '38px', fontSize: '13px', width: '100%', boxSizing: 'border-box' }}
                          >
                            {areas.map((a) => (
                              <option key={a} value={a}>{a}</option>
                            ))}
                          </select>
                        )}
                      </label>

                      {/* PREVIEW STANDAR REKSA */}
                      <div className="asset-preview-card">
                        <div>
                          <small style={{ color: 'var(--muted)' }}>Asset ID:</small>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                            <strong className="mono">{computedAssetId}</strong>
                            {isDuplicateHazardId ? (
                              <span style={{ fontSize: '11px', color: '#ef4444', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                                <AlertTriangle size={12} /> ID Terpakai ({duplicateHazard?.name})
                              </span>
                            ) : (
                              <span style={{ fontSize: '11px', color: '#16a34a', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                                <CheckCircle2 size={12} /> ID Unik
                              </span>
                            )}
                          </div>
                        </div>
                        <div>
                          <small style={{ color: 'var(--muted)' }}>BLE Beacon:</small>
                          <div><strong className="mono">{computedBeaconName}</strong></div>
                        </div>
                      </div>

                      <button
                        type="button"
                        className="button primary"
                        style={{ marginTop: '4px', fontSize: '13px', padding: '8px 14px' }}
                        disabled={createHazardMutation.isPending || !newHazardName.trim() || isDuplicateHazardId}
                        onClick={handleCreateHazardSubmit}
                      >
                        {createHazardMutation.isPending ? t.settings.creatorBtnSaving : t.settings.creatorBtnSave}
                      </button>
                    </div>
                  )}
                </div>

                {/* 3. UNIFIED REKSA IOT BINDING & FIRMWARE CARD */}
                <div className="unified-binding-card">
                  <div className="binding-header">
                    <div className="binding-header-title">
                      <Cpu size={16} color="#2563eb" />
                      <span>{t.settings.unifiedBindingTitle}</span>
                    </div>
                    <span className="binding-status-badge">
                      <span className="status-dot online" />
                      {t.settings.readyToPair}
                    </span>
                  </div>
                  <div className="binding-body">
                    <div className="binding-grid">
                      <div className="binding-item">
                        <span className="binding-item-label">{t.settings.labelHardwareId}</span>
                        <div className="binding-pill mono">{formDeviceId || '—'}</div>
                      </div>
                      <div className="binding-item">
                        <span className="binding-item-label">{t.settings.firmwareBeaconStandard}</span>
                        {formDeviceType === 'SMART_HELMET' ? (
                          <div className="binding-pill" style={{ color: '#64748b', fontSize: '12px' }}>
                            ESP32 WiFi + BLE Telemetry Gateway
                          </div>
                        ) : selectedHazard ? (
                          <button
                            type="button"
                            className="binding-copy-btn"
                            onClick={() => copyToClipboard(selectedHazard.beacon_name || `RK_${selectedHazard.category === 'MOBILE' ? 'M' : 'S'}_${selectedHazard.id.replace('-', '')}`)}
                            title={t.settings.firmwareCopyTooltip}
                          >
                            {copiedBeacon ? <Check size={12} color="#16a34a" /> : <Copy size={12} />}
                            {selectedHazard.beacon_name || `RK_${selectedHazard.category === 'MOBILE' ? 'M' : 'S'}_${selectedHazard.id.replace('-', '')}`}
                          </button>
                        ) : (
                          <span className="binding-pill" style={{ fontStyle: 'italic', color: 'var(--muted)', fontFamily: 'inherit', fontSize: '12px' }}>
                            Pilih target untuk generate BLE
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Safety Telemetry Profile Note */}
                    <div className="binding-note">
                      {formDeviceType === 'SMART_HELMET'
                        ? t.settings.firmwareHelmetNote
                        : selectedHazard?.category === 'MOBILE'
                        ? t.settings.firmwareMobileNote
                        : t.settings.firmwareStationaryNote}
                    </div>

                    {/* Collapsible Manual Hardware MAC Override */}
                    <div className="binding-footer-toggle">
                      <button
                        type="button"
                        onClick={() => setShowManualConfig(!showManualConfig)}
                        className="manual-config-toggle"
                      >
                        <SlidersHorizontal size={14} />
                        {showManualConfig ? t.settings.toggleManualConfigHide : t.settings.toggleManualConfig}
                      </button>

                      {(showManualConfig || isEditing) && (
                        <div className="manual-config-card" style={{ marginTop: '8px' }}>
                          <label>
                            <span>{t.settings.labelHardwareId}</span>
                            <input
                              type="text"
                              placeholder="e.g. DEV-BCN-M-FLK01, DEV-HLM-W01"
                              value={formDeviceId}
                              onChange={(e) => setFormDeviceId(e.target.value)}
                              disabled={isEditing}
                              required
                            />
                            <small>{t.settings.labelHardwareIdHelp}</small>
                          </label>

                          <label>
                            <span>{t.settings.labelAssignment}</span>
                            <input
                              type="text"
                              placeholder="e.g. Helmet Andy, Forklift Alpha"
                              value={formAssignment}
                              onChange={(e) => setFormAssignment(e.target.value)}
                            />
                          </label>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                {errorMsg && (
                  <div style={{ color: '#ef4444', fontSize: '13px', marginRight: 'auto', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <ShieldAlert size={16} /> {errorMsg}
                  </div>
                )}
                <button
                  type="button"
                  className="button secondary"
                  onClick={handleClosePairModal}
                >
                  {t.common.cancel}
                </button>
                <button
                  type="submit"
                  className="button primary"
                  disabled={pairMutation.isPending || !formDeviceId || !targetId}
                >
                  <Plus size={16} />
                  {pairMutation.isPending
                    ? t.settings.btnPairProcessing
                    : isEditing
                    ? t.settings.btnSaveDevice
                    : t.settings.btnPairRegister}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
