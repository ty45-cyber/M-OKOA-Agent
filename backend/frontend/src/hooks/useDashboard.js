/**
 * useDashboard — fetches all data for the dashboard in parallel.
 */
import { useCallback, useEffect, useState } from 'react'
import api from '../lib/api'
import { useTillStore } from '../store/till.store'

export function useDashboard() {
  const { setBalances, setLoading } = useTillStore()

  const [data, setData] = useState({
    balances: [],
    totalBalance: 0,
    recentTransactions: [],
    ledgerSummary: null,
    taxSummary: null,
  })
  const [error, setError] = useState(null)
  const [isLoading, setIsLoading] = useState(true)

  const fetchAll = useCallback(async () => {
    setIsLoading(true)
    setLoading(true)
    setError(null)

    try {
      const [balancesRes, transactionsRes, ledgerRes] = await Promise.allSettled([
        api.get('/api/v1/tills/balances/all'),
        api.get('/api/v1/transactions/?page_size=10'),
        api.get('/api/v1/transactions/summary/ledger'),
      ])

      const balances =
        balancesRes.status === 'fulfilled' ? balancesRes.value.data : []

      const total = balances.reduce(
        (sum, b) => sum + parseFloat(b.balance_kes || '0'),
        0
      )

      const recentTransactions =
        transactionsRes.status === 'fulfilled'
          ? transactionsRes.value.data.items
          : []

      const ledgerSummary =
        ledgerRes.status === 'fulfilled' ? ledgerRes.value.data : null

      setBalances(balances)
      setData({ balances, totalBalance: total, recentTransactions, ledgerSummary, taxSummary: null })
    } catch {
      setError('Failed to load dashboard data.')
    } finally {
      setIsLoading(false)
      setLoading(false)
    }
  }, [setBalances, setLoading])

  useEffect(() => { fetchAll() }, [fetchAll])

  return { data, error, isLoading, refetch: fetchAll }
}