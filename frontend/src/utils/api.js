import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
})

const handleError = (error) => {
  const message = error.response?.data?.detail || error.message
  console.error('[API Error]', message)
  
  const customError = new Error(message)
  customError.status = error.response?.status
  customError.code = error.code
  throw customError
}

api.interceptors.request.use(
  (config) => {
    if (import.meta.env.DEV) {
      console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`)
    }
    return config
  },
  (error) => Promise.reject(error)
)

api.interceptors.response.use(
  (response) => response.data,
  (error) => handleError(error)
)

const withRetry = async (apiCall, retries = 3) => {
  for (let i = 0; i < retries; i++) {
    try {
      return await apiCall()
    } catch (error) {
      if (i === retries - 1) throw error
      await new Promise(r => setTimeout(r, 1000 * (i + 1)))
    }
  }
}

export const videoApi = {
  async getVideoInfo(url) {
    return withRetry(() => api.post('/video/info', { url }))
  },

  async startDownload(url, quality = 'best', recordId = null) {
    return withRetry(() => api.post('/video/download', { 
      url, 
      quality, 
      record_id: recordId 
    }))
  },

  async retryDownload(recordId, quality = 'best') {
    return withRetry(() => api.post('/video/retry', { 
      record_id: recordId, 
      quality 
    }))
  },
}

export const downloadApi = {
  async getDownloads(limit = 50) {
    return withRetry(() => api.get('/downloads', { params: { limit } }))
  },

  async searchDownloads(query, limit = 50) {
    return withRetry(() => api.get('/downloads/search', { 
      params: { query, limit } 
    }))
  },

  async deleteDownload(id) {
    return withRetry(() => api.delete(`/downloads/${id}`))
  },

  async clearDownloads() {
    return withRetry(() => api.delete('/downloads'))
  },
}

export const settingsApi = {
  async getSettings() {
    return withRetry(() => api.get('/settings'))
  },

  async updateSettings(settings) {
    return withRetry(() => api.put('/settings', settings))
  },
}

export function createWebSocket(downloadId) {
  const wsBaseUrl = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000/api'
  return new WebSocket(`${wsBaseUrl}/ws/download/${downloadId}`)
}
