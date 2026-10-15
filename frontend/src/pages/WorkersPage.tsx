import { useState, useMemo, useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Search, Plus, Trash2, Edit2, Shield, Activity, HardHat, Users, MoreVertical, X, Check, AlertTriangle } from 'lucide-react'
import { api, getErrorMessage } from '../services/api'
import { LoadingState, ErrorState, EmptyState } from '../components/common/States'
import { Panel } from '../components/common/Panel'
import { KpiCard } from '../components/dashboard/KpiCard'
import { Pagination } from '../components/common/Pagination'
import { useTranslation } from '../i18n'
import { useCatalogOptions } from '../hooks/useCatalogOptions'
import type { Worker, Device } from '../types'

export default function WorkersPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const pageSize = 6

  const [workerId, setWorkerId] = useState('')
  const [name, setName] = useState('')
  const [role, setRole] = useState('Operator')
  const [area, setArea] = useState('Gudang Utama')
  const [isEditing, setIsEditing] = useState(false)
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState('')
  const [errorMsg, setErrorMsg] = useState('')
  const menuRef = useRef<HTMLDivElement | null>(null)

  const workersQuery = useQuery({
    queryKey: ['workers'],
    queryFn: () => api<{ items: Worker[] }>('/workers')
  })

  const { roles, areas, addRole, addArea } = useCatalogOptions(workersQuery.data?.items || [])
  const [isAddingRole, setIsAddingRole] = useState(false)
  const [newRoleInput, setNewRoleInput] = useState('')
  const [isAddingArea, setIsAddingArea] = useState(false)
  const [newAreaInput, setNewAreaInput] = useState('')

  const rawWorkers = useMemo(() => workersQuery.data?.items ?? [], [workersQuery.data])

  const isDuplicateWorkerId = useMemo(() => {
    if (isEditing || !workerId.trim()) return false
    return rawWorkers.some((w) => w.id.toUpperCase() === workerId.trim().toUpperCase())
  }, [isEditing, workerId, rawWorkers])

  const duplicateWorker = useMemo(() => {
    if (!isDuplicateWorkerId) return null
    return rawWorkers.find((w) => w.id.toUpperCase() === workerId.trim().toUpperCase())
  }, [isDuplicateWorkerId, workerId, rawWorkers])

  const suggestedNextId = useMemo(() => {
    const nums = rawWorkers
      .map((w) => {
        const match = w.id.match(/^W?(\d+)$/i)
        return match ? parseInt(match[1], 10) : 0
      })
      .filter((n) => n > 0)
    const maxNum = nums.length > 0 ? Math.max(...nums) : 0
    return `W${String(maxNum + 1).padStart(2, '0')}`
  }, [rawWorkers])

  const handleSaveNewRole = () => {
    const clean = newRoleInput.trim()
    if (clean) {
      addRole(clean)
      setRole(clean)
      setNewRoleInput('')
      setIsAddingRole(false)
    }
  }

  const handleSaveNewArea = () => {
    const clean = newAreaInput.trim()
    if (clean) {
      addArea(clean)
      setArea(clean)
      setNewAreaInput('')
      setIsAddingArea(false)
    }
  }

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
      void queryClient.invalidateQueries({ queryKey: ['devices'] })
      void queryClient.invalidateQueries({ queryKey: ['summary'] })
      setSuccessMsg(res.message || t.workers.toastCreated)
      setErrorMsg('')
      setWorkerId('')
      setName('')
      setIsEditing(false)
      setIsAddingRole(false)
      setIsAddingArea(false)
      setTimeout(() => setSuccessMsg(''), 3000)
    },
    onError: (err: unknown) => {
      setErrorMsg(getErrorMessage(err, 'Gagal mendaftarkan pekerja'))
      setSuccessMsg('')
    }
  })

  const updateWorkerMutation = useMutation({
    mutationFn: (data: { id: string; name: string; role: string; area: string }) =>
      api<{ worker: Worker; message: string }>(`/workers/${data.id}`, {
        method: 'PUT',
        body: JSON.stringify(data)
      }),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: ['workers'] })
      void queryClient.invalidateQueries({ queryKey: ['devices'] })
      void queryClient.invalidateQueries({ queryKey: ['summary'] })
      setSuccessMsg(res.message || t.workers.toastUpdated)
      setErrorMsg('')
      setWorkerId('')
      setName('')
      setIsEditing(false)
      setIsAddingRole(false)
      setIsAddingArea(false)
      setTimeout(() => setSuccessMsg(''), 3000)
    },
    onError: (err: unknown) => {
      setErrorMsg(getErrorMessage(err, 'Gagal memperbarui data pekerja'))
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
      void queryClient.invalidateQueries({ queryKey: ['devices'] })
      void queryClient.invalidateQueries({ queryKey: ['summary'] })
      setSuccessMsg(res.message || t.workers.toastDeleted)
      setErrorMsg('')
      setTimeout(() => setSuccessMsg(''), 3000)
    },
    onError: (err: unknown) => {
      setErrorMsg(getErrorMessage(err, 'Gagal menghapus pekerja'))
      setSuccessMsg('')
    }
  })

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!workerId || !name) {
      setErrorMsg(t.workers.requiredFields)
      return
    }

    if (isEditing) {
      updateWorkerMutation.mutate({
        id: workerId.trim().toUpperCase(),
        name: name.trim(),
        role,
        area
      })
    } else {
      createWorkerMutation.mutate({
        id: workerId.trim().toUpperCase(),
        name: name.trim(),
        role,
        area
      })
    }
  }

  const handleEditClick = (w: Worker) => {
    setActiveMenuId(null)
    setIsEditing(true)
    setWorkerId(w.id)
    setName(w.name)
    setRole(w.role || 'Operator')
    setArea(w.area || 'Gudang Utama')
    setErrorMsg('')
    setSuccessMsg('')
  }

  const handleDeleteClick = (id: string, workerName: string) => {
    setActiveMenuId(null)
    if (window.confirm(t.workers.confirmDelete(workerName, id))) {
      deleteWorkerMutation.mutate(id)
    }
  }

  const cancelEdit = () => {
    setIsEditing(false)
    setWorkerId('')
    setName('')
    setRole(roles[0] || 'Operator')
    setArea(areas[0] || 'Gudang Utama')
    setIsAddingRole(false)
    setIsAddingArea(false)
    setNewRoleInput('')
    setNewAreaInput('')
    setErrorMsg('')
  }

  const filteredWorkers = useMemo(() => {
    return workersQuery.data?.items.filter((w) =>
      w.name.toLowerCase().includes(search.toLowerCase()) ||
      w.id.toLowerCase().includes(search.toLowerCase()) ||
      w.role.toLowerCase().includes(search.toLowerCase())
    ) ?? []
  }, [workersQuery.data, search])

  const totalPages = Math.ceil(filteredWorkers.length / pageSize) || 1
  const paginatedWorkers = useMemo(() => {
    const start = (page - 1) * pageSize
    return filteredWorkers.slice(start, start + pageSize)
  }, [filteredWorkers, page, pageSize])

  useEffect(() => {
    if (page > totalPages) {
      setPage(1)
    }
  }, [totalPages, page])

  if (workersQuery.isLoading) return <LoadingState />
  if (workersQuery.isError) return <ErrorState retry={() => void workersQuery.refetch()} />

  const totalWorkers = workersQuery.data?.items.length ?? 0
  const onlineCount = workersQuery.data?.items.filter((w) => w.online).length ?? 0
  const avgRisk = totalWorkers > 0 
    ? Math.round(workersQuery.data!.items.reduce((sum, w) => sum + w.risk_score, 0) / totalWorkers) 
    : 0

  return (
    <div className="stack-lg wide-page workers-page">
      <div className="kpi-grid">
        <KpiCard
          label={t.workers.kpiTotal}
          value={totalWorkers}
          detail={t.workers.kpiTotalDetail}
          icon={Users}
          tone="blue"
        />
        <KpiCard
          label={t.workers.kpiHelmets}
          value={onlineCount}
          detail={t.workers.kpiHelmetsOffline(totalWorkers - onlineCount)}
          icon={HardHat}
          tone="green"
        />
        <KpiCard
          label={t.workers.kpiAvgRisk}
          value={avgRisk}
          unit="/100"
          detail={
            avgRisk >= 70
              ? t.workers.kpiStatusCritical
              : avgRisk >= 40
              ? t.workers.kpiStatusWarning
              : t.workers.kpiStatusControlled
          }
          icon={Shield}
          tone={avgRisk >= 70 ? 'red' : avgRisk >= 40 ? 'orange' : 'green'}
        />
      </div>

      <div className="device-registry-grid">
        <div className="stack-md">
          <Panel
            title={t.workers.panelTitle}
            subtitle={t.workers.panelSubtitle}
            className="workforce-panel"
            action={
              <div className="search-box">
                <Search size={16} />
                <input
                  type="text"
                  placeholder={t.workers.searchPlaceholder}
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value)
                    setPage(1)
                  }}
                />
              </div>
            }
          >
            {filteredWorkers.length === 0 ? (
              <EmptyState label={t.workers.empty} />
            ) : (
              <>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>{t.workers.colWorker}</th>
                        <th>{t.workers.colRole}</th>
                        <th>{t.workers.colArea}</th>
                        <th>{t.workers.colDevice}</th>
                        <th>{t.workers.colStatus}</th>
                        <th style={{ textAlign: 'right' }}>{t.workers.colAction}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {paginatedWorkers.map((w, index) => {
                        const matchedDevice = devicesQuery.data?.items.find(
                          (d) =>
                            (d.type === 'SMART_HELMET' || d.id.includes('HLM')) &&
                            (d.topic?.includes(`/helmet/${w.id}/`) || d.id.includes(w.id) || d.assignment === w.name)
                        )
                        return (
                          <tr
                            key={w.id}
                            className="clickable-row"
                            onClick={() => navigate(`/workers/${w.id}`)}
                            title={t.workers.rowClickTooltip}
                          >
                            <td>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
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
                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '12px', fontWeight: 600, color: 'var(--text)' }}>
                                  <HardHat size={16} style={{ color: 'var(--blue)' }} /> {matchedDevice.id}
                                </span>
                              ) : (
                                <span style={{ fontSize: '12px', color: 'var(--muted)' }}>{t.workers.noHelmet}</span>
                              )}
                            </td>
                            <td>
                              <span className={`online-label ${!w.online ? 'offline' : ''}`}>
                                <i /> {w.online ? t.common.online : t.common.offline}
                              </span>
                            </td>
                            <td
                              style={{ textAlign: 'right' }}
                              onClick={(e) => e.stopPropagation()}
                            >
                              <div
                                className="action-menu-container"
                                ref={activeMenuId === w.id ? menuRef : null}
                              >
                                <button
                                  className="action-btn"
                                  title={t.workers.actionMenuTooltip}
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    setActiveMenuId(activeMenuId === w.id ? null : w.id)
                                  }}
                                >
                                  <MoreVertical size={16} />
                                </button>

                                {activeMenuId === w.id && (
                                  <div className={`action-menu-dropdown ${index >= paginatedWorkers.length - 2 && paginatedWorkers.length > 2 ? 'dropdown-up' : ''}`}>
                                    <button
                                      className="action-menu-item"
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        handleEditClick(w)
                                      }}
                                    >
                                      <Edit2 size={14} style={{ color: 'var(--blue)' }} />
                                      <span>{t.workers.menuEdit}</span>
                                    </button>
                                    <button
                                      className="action-menu-item danger"
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        handleDeleteClick(w.id, w.name)
                                      }}
                                    >
                                      <Trash2 size={14} />
                                      <span>{t.workers.menuDelete}</span>
                                    </button>
                                  </div>
                                )}
                              </div>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={page}
                  totalPages={totalPages}
                  totalItems={filteredWorkers.length}
                  pageSize={pageSize}
                  onPageChange={setPage}
                  itemName={t.workers.itemUnit}
                />
              </>
            )}
          </Panel>
        </div>

        <div className="device-form-panel">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <h3 style={{ margin: 0 }}>
              {isEditing ? t.workers.formEditTitle : t.workers.formRegisterTitle}
            </h3>
            {isEditing && (
              <button
                type="button"
                className="action-btn"
                onClick={cancelEdit}
                title={t.common.cancel}
              >
                <X size={16} />
              </button>
            )}
          </div>
          <p style={{ fontSize: '12px', color: 'var(--muted)', margin: '0 0 20px 0', lineHeight: 1.4 }}>
            {isEditing
              ? t.workers.formEditDesc(name, workerId)
              : t.workers.formRegisterDesc}
          </p>

          <form onSubmit={handleFormSubmit} className="device-form">
            <label>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>{t.workers.labelId}</span>
                {!isEditing && suggestedNextId && !workerId && (
                  <button
                    type="button"
                    className="btn-inline-add"
                    onClick={() => setWorkerId(suggestedNextId)}
                    title={t.workers.tooltipUseSuggestedId}
                  >
                    {t.workers.btnUseSuggestedId(suggestedNextId)}
                  </button>
                )}
              </div>
              <input
                type="text"
                placeholder={suggestedNextId ? t.workers.suggestedIdPlaceholder(suggestedNextId) : t.workers.labelIdPlaceholder}
                value={workerId}
                onChange={(e) => setWorkerId(e.target.value)}
                disabled={isEditing}
                style={isEditing ? { opacity: 0.7, cursor: 'not-allowed' } : undefined}
                required
              />
              {isDuplicateWorkerId && (
                <span style={{ fontSize: '11px', color: '#ef4444', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px', marginTop: '4px' }}>
                  <AlertTriangle size={13} /> ID "{workerId.toUpperCase()}" sudah terdaftar untuk {duplicateWorker?.name}. Gunakan ID unik!
                </span>
              )}
            </label>

            <label>
              <span>{t.workers.labelName}</span>
              <input
                type="text"
                placeholder={t.workers.labelNamePlaceholder}
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </label>

            <div>
              <label>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>{t.workers.labelRole}</span>
                  <button
                    type="button"
                    className="btn-inline-add"
                    onClick={() => {
                      setIsAddingRole(!isAddingRole)
                      setNewRoleInput('')
                    }}
                  >
                    <Plus size={14} /> {t.workers.addNewRole}
                  </button>
                </div>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                >
                  {roles.map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </label>

              {isAddingRole && (
                <div className="inline-creator-card">
                  <div className="inline-creator-card-header">
                    <span>{t.workers.addNewRole}</span>
                    <button
                      type="button"
                      onClick={() => setIsAddingRole(false)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748b' }}
                    >
                      <X size={14} />
                    </button>
                  </div>
                  <input
                    type="text"
                    placeholder={t.workers.rolePlaceholder}
                    value={newRoleInput}
                    onChange={(e) => setNewRoleInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        handleSaveNewRole()
                      }
                    }}
                    autoFocus
                    style={{ height: '36px', fontSize: '13px' }}
                  />
                  <div className="inline-creator-actions">
                    <button
                      type="button"
                      className="button primary"
                      style={{ height: '32px', fontSize: '12px', padding: '0 12px' }}
                      disabled={!newRoleInput.trim()}
                      onClick={handleSaveNewRole}
                    >
                      <Check size={14} /> {t.workers.btnSaveAndUse}
                    </button>
                    <button
                      type="button"
                      className="button secondary"
                      style={{ height: '32px', fontSize: '12px', padding: '0 12px' }}
                      onClick={() => setIsAddingRole(false)}
                    >
                      {t.common.cancel}
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div>
              <label>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>{t.workers.labelArea}</span>
                  <button
                    type="button"
                    className="btn-inline-add"
                    onClick={() => {
                      setIsAddingArea(!isAddingArea)
                      setNewAreaInput('')
                    }}
                  >
                    <Plus size={14} /> {t.workers.addNewArea}
                  </button>
                </div>
                <select
                  value={area}
                  onChange={(e) => setArea(e.target.value)}
                >
                  {areas.map((a) => (
                    <option key={a} value={a}>{a}</option>
                  ))}
                </select>
              </label>

              {isAddingArea && (
                <div className="inline-creator-card">
                  <div className="inline-creator-card-header">
                    <span>{t.workers.addNewArea}</span>
                    <button
                      type="button"
                      onClick={() => setIsAddingArea(false)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748b' }}
                    >
                      <X size={14} />
                    </button>
                  </div>
                  <input
                    type="text"
                    placeholder={t.workers.areaPlaceholder}
                    value={newAreaInput}
                    onChange={(e) => setNewAreaInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        handleSaveNewArea()
                      }
                    }}
                    autoFocus
                    style={{ height: '36px', fontSize: '13px' }}
                  />
                  <div className="inline-creator-actions">
                    <button
                      type="button"
                      className="button primary"
                      style={{ height: '32px', fontSize: '12px', padding: '0 12px' }}
                      disabled={!newAreaInput.trim()}
                      onClick={handleSaveNewArea}
                    >
                      <Check size={14} /> {t.workers.btnSaveAndUse}
                    </button>
                    <button
                      type="button"
                      className="button secondary"
                      style={{ height: '32px', fontSize: '12px', padding: '0 12px' }}
                      onClick={() => setIsAddingArea(false)}
                    >
                      {t.common.cancel}
                    </button>
                  </div>
                </div>
              )}
            </div>

            {successMsg && (
              <div style={{ color: '#059669', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600 }}>
                <Activity size={16} /> {successMsg}
              </div>
            )}

            {errorMsg && (
              <div style={{ color: '#ef4444', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600 }}>
                <Shield size={16} /> {errorMsg}
              </div>
            )}

            <div style={{ display: 'flex', gap: '8px' }}>
              {isEditing && (
                <button
                  type="button"
                  className="button secondary"
                  onClick={cancelEdit}
                  style={{ flex: 1 }}
                >
                  {t.common.cancel}
                </button>
              )}
              <button
                type="submit"
                className="button primary"
                disabled={createWorkerMutation.isPending || updateWorkerMutation.isPending || isDuplicateWorkerId}
                style={{ flex: isEditing ? 2 : 1, width: isEditing ? 'auto' : '100%' }}
              >
                {isEditing ? (
                  <>
                    <Edit2 size={16} />
                    {updateWorkerMutation.isPending ? t.workers.btnSaving : t.workers.btnSaveEdit}
                  </>
                ) : (
                  <>
                    <Plus size={16} />
                    {createWorkerMutation.isPending ? t.workers.btnRegistering : t.workers.btnRegister}
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
