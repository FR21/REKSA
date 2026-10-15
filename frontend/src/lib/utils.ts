export function levelLabel(level: string, lang: 'id' | 'en' = 'id') {
  if (lang === 'en') {
    return { SAFE: 'Safe', MODERATE: 'Moderate', HIGH: 'High', CRITICAL: 'Critical' }[level] ?? level
  }
  return { SAFE: 'Aman', MODERATE: 'Moderat', HIGH: 'Tinggi', CRITICAL: 'Kritis' }[level] ?? level
}

export function formatDate(value: string, lang: 'id' | 'en' = 'id') {
  return new Intl.DateTimeFormat(lang === 'id' ? 'id-ID' : 'en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}
