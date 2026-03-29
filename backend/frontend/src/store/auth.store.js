/**
 * Auth store — Zustand global state for user identity.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { clearTokens, storeTokens } from '../lib/api'

export const useAuthStore = create(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,

      setUser: (user, access, refresh) => {
        storeTokens(access, refresh)
        set({ user, isAuthenticated: true })
      },

      logout: () => {
        clearTokens()
        set({ user: null, isAuthenticated: false })
      },
    }),
    {
      name: 'mokoa-auth',
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)