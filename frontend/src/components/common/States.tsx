import { AlertCircle, DatabaseZap, LoaderCircle } from 'lucide-react'

export function LoadingState({ label = 'Memuat data...' }: { label?: string }) {
  return <div className="state-box"><LoaderCircle className="spin" size={24} /><span>{label}</span></div>
}

export function ErrorState({ retry }: { retry?: () => void }) {
  return <div className="state-box error"><AlertCircle size={24} /><strong>Data tidak dapat dimuat</strong><span>Periksa koneksi backend lalu coba lagi.</span>{retry && <button className="button secondary" onClick={retry}>Coba lagi</button>}</div>
}

export function EmptyState({ label = 'Belum ada data untuk ditampilkan.' }: { label?: string }) {
  return <div className="state-box"><DatabaseZap size={24} /><span>{label}</span></div>
}

