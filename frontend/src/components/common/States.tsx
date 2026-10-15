import { AlertCircle, DatabaseZap, LoaderCircle } from 'lucide-react'
import { useTranslation } from '../../i18n'

export function LoadingState({ label }: { label?: string }) {
  const { t } = useTranslation()
  return (
    <div className="state-box">
      <LoaderCircle className="spin" size={24} />
      <span>{label || t.common.loading}</span>
    </div>
  )
}

export function ErrorState({ retry }: { retry?: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="state-box error">
      <AlertCircle size={24} />
      <strong>{t.common.error}</strong>
      <span>{t.common.errorSubtitle}</span>
      {retry && (
        <button className="button secondary" onClick={retry}>
          {t.common.retry}
        </button>
      )}
    </div>
  )
}

export function EmptyState({ label }: { label?: string }) {
  const { t } = useTranslation()
  return (
    <div className="state-box">
      <DatabaseZap size={24} />
      <span>{label || t.common.noData}</span>
    </div>
  )
}
