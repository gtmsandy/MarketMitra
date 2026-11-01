import { createContext } from 'react'

import type { IdentityUser } from '../api/auth'

export type AuthStatus = 'checking' | 'anonymous' | 'authenticated'

export type AuthContextValue = {
  status: AuthStatus
  user: IdentityUser | null
  login: (email: string, password: string) => Promise<void>
  register: (email: string, displayName: string, password: string) => Promise<void>
  logout: () => Promise<void>
  updateProfile: (displayName: string) => Promise<void>
}

export const AuthContext = createContext<AuthContextValue>({
  status: 'anonymous',
  user: null,
  login: async () => undefined,
  register: async () => undefined,
  logout: async () => undefined,
  updateProfile: async () => undefined,
})
