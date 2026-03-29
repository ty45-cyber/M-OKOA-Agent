/**
 * Till store — cached balances and till list.
 */
import { create } from 'zustand'

export const useTillStore = create((set) => ({
  tills: [],
  balances: [],
  totalBalance: 0,
  isLoading: false,

  setTills: (tills) => set({ tills }),

  setBalances: (balances) => {
    const total = balances.reduce(
      (sum, b) => sum + parseFloat(b.balance_kes || '0'),
      0
    )
    set({ balances, totalBalance: total })
  },

  setLoading: (isLoading) => set({ isLoading }),
}))