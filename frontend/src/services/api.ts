const API_URL = import.meta.env.VITE_API_URL || '/api/v1'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  if (!response.ok) {
    const data = (await response.json().catch(() => ({ detail: 'Terjadi kesalahan' }))) as { detail?: string }
    throw new ApiError(response.status, data.detail ?? 'Terjadi kesalahan')
  }
  return response.json() as Promise<T>
}

export function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

export { API_URL }
