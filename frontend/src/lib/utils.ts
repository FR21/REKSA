export function levelLabel(level: string) {
  return { SAFE: 'Aman', MODERATE: 'Moderat', HIGH: 'Tinggi', CRITICAL: 'Kritis' }[level] ?? level
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat('id-ID', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}
