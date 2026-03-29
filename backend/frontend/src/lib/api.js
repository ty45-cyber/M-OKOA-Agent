/**
 * Axios API client — JWT injection, token refresh, error normalisation.
 */
import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

// Inject access token on every request
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('mokoa_access_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Auto-refresh on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config

    if (error.response?.status === 401 && !original._retried) {
      original._retried = true
      const refreshToken = localStorage.getItem('mokoa_refresh_token')

      if (!refreshToken) {
        clearTokens()
        window.location.href = '/login'
        return Promise.reject(error)
      }

      try {
        const { data } = await axios.post(`${BASE_URL}/api/v1/auth/refresh`, {
          refresh_token: refreshToken,
        })
        storeTokens(data.access_token, data.refresh_token)
        original.headers.Authorization = `Bearer ${data.access_token}`
        return api(original)
      } catch {
        clearTokens()
        window.location.href = '/login'
        return Promise.reject(error)
      }
    }

    return Promise.reject(error)
  }
)

export function storeTokens(access, refresh) {
  localStorage.setItem('mokoa_access_token', access)
  localStorage.setItem('mokoa_refresh_token', refresh)
}

export function clearTokens() {
  localStorage.removeItem('mokoa_access_token')
  localStorage.removeItem('mokoa_refresh_token')
}

export function getAccessToken() {
  return localStorage.getItem('mokoa_access_token')
}

export default api