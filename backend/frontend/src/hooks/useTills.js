/**
 * useTills — full CRUD + balance + smart float operations.
 */
import { useCallback, useEffect, useState } from 'react'
import api from '../lib/api'

export function useTills() {
  const [tills, setTills] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchTills = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const { data } = await api.get('/api/v1/tills/')
      setTills(data)
    } catch {
      setError('Failed to load tills.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => { fetchTills() }, [fetchTills])

  const createTill = useCallback(async (payload) => {
    const { data } = await api.post('/api/v1/tills/', payload)
    await fetchTills()
    return data
  }, [fetchTills])

  const updateTill = useCallback(async (publicId, payload) => {
    const { data } = await api.patch(`/api/v1/tills/${publicId}`, payload)
    await fetchTills()
    return data
  }, [fetchTills])

  const deactivateTill = useCallback(async (publicId) => {
    await api.delete(`/api/v1/tills/${publicId}`)
    await fetchTills()
  }, [fetchTills])

  const queryBalance = useCallback(async (publicId, forceRefresh = false) => {
    const { data } = await api.get(
      `/api/v1/tills/${publicId}/balance?force_refresh=${forceRefresh}`
    )
    return data
  }, [])

  const addSmartFloatRule = useCallback(async (tillPublicId, payload) => {
    const { data } = await api.post(
      `/api/v1/tills/${tillPublicId}/smart-float-rules`,
      payload
    )
    return data
  }, [])

  return {
    tills, isLoading, error,
    fetchTills, createTill, updateTill,
    deactivateTill, queryBalance, addSmartFloatRule,
  }
}