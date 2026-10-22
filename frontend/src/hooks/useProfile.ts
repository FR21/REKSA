import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import type { UserProfile } from '../types'

export function getInitials(name: string): string {
  const parts = name.trim().split(' ').filter(Boolean)
  if (parts.length > 1) {
    return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
  }
  return (name.trim().slice(0, 2) || 'US').toUpperCase()
}

export function getFirstName(name: string): string {
  const parts = name.trim().split(' ').filter(Boolean)
  return parts[0] || name.trim() || 'Supervisor'
}

export function useProfile() {
  const queryClient = useQueryClient()

  const profileQuery = useQuery({
    queryKey: ['profile'],
    queryFn: () => api<UserProfile>('/profile'),
    staleTime: 60_000,
    initialData: () => {
      try {
        const saved = localStorage.getItem('reksa_user_profile')
        if (saved) return JSON.parse(saved) as UserProfile
      } catch {
        // fallback
      }
      return { name: 'Raka Wijaya', role: 'Supervisor K3', initials: 'RW' }
    },
  })

  const updateProfileMutation = useMutation({
    mutationFn: async (data: { name: string; role: string }) => {
      try {
        return await api<UserProfile>('/profile', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
        })
      } catch {
        return {
          name: data.name,
          role: data.role,
          initials: getInitials(data.name),
        }
      }
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(['profile'], updated)
      void queryClient.invalidateQueries({ queryKey: ['profile'] })
      try {
        localStorage.setItem('reksa_user_profile', JSON.stringify(updated))
      } catch {
        // ignore
      }
    },
  })

  const profile = profileQuery.data ?? { name: 'Raka Wijaya', role: 'Supervisor K3', initials: 'RW' }
  const firstName = getFirstName(profile.name)

  return {
    profile,
    firstName,
    isLoading: profileQuery.isLoading,
    updateProfile: updateProfileMutation.mutateAsync,
    isUpdating: updateProfileMutation.isPending,
  }
}
