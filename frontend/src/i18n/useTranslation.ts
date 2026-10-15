import { useContext } from 'react'
import { LanguageContext, defaultContextValue } from './context'

export function useTranslation() {
  const context = useContext(LanguageContext)
  return context || defaultContextValue
}
