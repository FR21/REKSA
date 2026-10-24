import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { RiskBadge } from '../src/components/common/RiskBadge'

describe('RiskBadge', () => {
  it('renders text and accessible risk state', () => {
    render(<RiskBadge level="CRITICAL" />)
    expect(screen.getByText('Kritis')).toBeInTheDocument()
    expect(screen.getByLabelText('Risiko Kritis')).toBeInTheDocument()
  })

  it('renders Recovery / Pemulihan badge correctly', () => {
    render(<RiskBadge level="RECOVERY" />)
    expect(screen.getByText('Pemulihan')).toBeInTheDocument()
    expect(screen.getByLabelText('Risiko Pemulihan')).toBeInTheDocument()
  })
})

