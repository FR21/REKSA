import { createContext } from 'react'
import type { Language, TranslationSchema } from './types'
import { id } from './locales/id'

export interface LanguageContextValue {
  language: Language
  setLanguage: (lang: Language) => void
  t: TranslationSchema
}

export const defaultContextValue: LanguageContextValue = {
  language: 'id',
  setLanguage: () => {},
  t: id,
}

export const LanguageContext = createContext<LanguageContextValue>(defaultContextValue)
