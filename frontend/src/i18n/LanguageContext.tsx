import { useState, useEffect, useMemo, type ReactNode } from 'react'
import type { Language, TranslationSchema } from './types'
import { id } from './locales/id'
import { en } from './locales/en'
import { LanguageContext } from './context'

const dictionaries: Record<Language, TranslationSchema> = {
  id,
  en,
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() => {
    try {
      const saved = localStorage.getItem('reksa_language')
      if (saved === 'id' || saved === 'en') return saved
    } catch {
      // fallback
    }
    return 'id'
  })

  const setLanguage = (lang: Language) => {
    setLanguageState(lang)
    try {
      localStorage.setItem('reksa_language', lang)
      document.documentElement.lang = lang
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  const t = useMemo(() => dictionaries[language] ?? dictionaries.id, [language])

  const value = useMemo(
    () => ({
      language,
      setLanguage,
      t,
    }),
    [language, t]
  )

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}
