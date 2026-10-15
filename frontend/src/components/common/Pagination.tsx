import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useTranslation } from '../../i18n'

interface PaginationProps {
  currentPage: number
  totalPages: number
  totalItems: number
  pageSize: number
  onPageChange: (page: number) => void
  itemName?: string
}

export function Pagination({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
  itemName,
}: PaginationProps) {
  const { t } = useTranslation()

  if (totalPages <= 1) return null

  const startItem = (currentPage - 1) * pageSize + 1
  const endItem = Math.min(currentPage * pageSize, totalItems)

  const pages: (number | string)[] = []
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) {
      pages.push(i)
    }
  } else {
    pages.push(1)
    if (currentPage > 3) {
      pages.push('...')
    }
    const start = Math.max(2, currentPage - 1)
    const end = Math.min(totalPages - 1, currentPage + 1)
    for (let i = start; i <= end; i++) {
      pages.push(i)
    }
    if (currentPage < totalPages - 2) {
      pages.push('...')
    }
    pages.push(totalPages)
  }

  return (
    <div className="pagination-wrapper">
      <div className="pagination-info">
        {t.common.showingRange(startItem, endItem, totalItems, itemName)}
      </div>
      <div className="pagination-controls">
        <button
          className="pagination-btn prev-next"
          disabled={currentPage === 1}
          onClick={() => onPageChange(currentPage - 1)}
          aria-label={t.common.prevPageAria}
          title={t.common.prevPageAria}
        >
          <ChevronLeft size={16} />
        </button>

        {pages.map((p, idx) =>
          typeof p === 'number' ? (
            <button
              key={p}
              className={`pagination-btn ${currentPage === p ? 'active' : ''}`}
              onClick={() => onPageChange(p)}
              aria-current={currentPage === p ? 'page' : undefined}
            >
              {p}
            </button>
          ) : (
            <span key={`dots-${idx}`} className="pagination-ellipsis">
              ...
            </span>
          )
        )}

        <button
          className="pagination-btn prev-next"
          disabled={currentPage === totalPages}
          onClick={() => onPageChange(currentPage + 1)}
          aria-label={t.common.nextPageAria}
          title={t.common.nextPageAria}
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  )
}
