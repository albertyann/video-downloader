import axios from 'axios'

const API_BASE_URL = 'http://localhost:8000/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const videoApi = {
  async getVideoInfo(url) {
    const response = await api.post('/video/info', { url })
    return response.data
  },

  async startDownload(url, quality = 'best', recordId = null) {
    const response = await api.post('/video/download', { url, quality, record_id: recordId })
    return response.data
  },

  async retryDownload(recordId, quality = 'best') {
    const response = await api.post('/video/retry', { record_id: recordId, quality })
    return response.data
  },
}

export const downloadApi = {
  async getDownloads(limit = 50) {
    const response = await api.get('/downloads', { params: { limit } })
    return response.data
  },

  async searchDownloads(query, limit = 50) {
    const response = await api.get('/downloads/search', { params: { query, limit } })
    return response.data
  },

  async deleteDownload(id) {
    const response = await api.delete(`/downloads/${id}`)
    return response.data
  },

  async clearDownloads() {
    const response = await api.delete('/downloads')
    return response.data
  },
}

export const settingsApi = {
  async getSettings() {
    const response = await api.get('/settings')
    return response.data
  },

  async updateSettings(settings) {
    const response = await api.put('/settings', settings)
    return response.data
  },
}

export function createWebSocket(downloadId) {
  return new WebSocket(`ws://localhost:8000/api/ws/download/${downloadId}`)
}
