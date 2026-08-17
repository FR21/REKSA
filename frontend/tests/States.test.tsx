import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EmptyState, ErrorState, LoadingState } from '../src/components/common/States'

describe('data states', () => {
  it('renders loading, empty, and error messaging', () => {
    const { rerender } = render(<LoadingState />)
    expect(screen.getByText('Memuat data...')).toBeInTheDocument()
    rerender(<EmptyState />)
    expect(screen.getByText(/Belum ada data/)).toBeInTheDocument()
    rerender(<ErrorState />)
    expect(screen.getByText('Data tidak dapat dimuat')).toBeInTheDocument()
  })
})

