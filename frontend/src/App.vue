<template>
  <div class="min-h-screen p-4 md:p-8">
    <div class="max-w-4xl mx-auto space-y-6">
      <!-- Header -->
      <header class="text-center mb-8">
        <h1 class="text-4xl font-bold text-white mb-2">📹 Video Downloader</h1>
        <p class="text-gray-400">Download videos from 1000+ sites with domain-specific proxy support</p>
      </header>
      
      <!-- URL Input -->
      <VideoInput
        :loading="isFetching"
        @fetch="handleFetchInfo"
      />
      
      <!-- Video Info -->
      <VideoInfo
        v-if="videoInfo"
        :info="videoInfo"
        v-model:quality="selectedQuality"
      />
      
      <!-- Download Progress -->
      <DownloadProgress
        v-if="videoInfo"
        :is-downloading="isDownloading"
        :is-complete="isComplete"
        :disabled="isDownloading"
        :status="currentStatus"
        :progress="downloadProgress"
        :speed="downloadSpeed"
        :eta="downloadEta"
        :error="downloadError"
        :status-text="statusText"
        @download="handleDownload"
        @retry="handleRetry"
      />
      
      <!-- History -->
      <HistoryList
        :downloads="downloads"
        @search="handleSearch"
        @clear="handleClearHistory"
        @delete="handleDeleteDownload"
        @retry="handleRetryFromHistory"
        @download-item="handleDownloadFromHistory"
      />
      
      <!-- Settings Button -->
      <div class="fixed bottom-6 right-6">
        <button
          @click="showSettings = true"
          class="bg-secondary hover:bg-gray-600 text-white p-4 rounded-full shadow-lg transition-colors"
        >
          ⚙️
        </button>
      </div>
      
      <!-- Settings Modal -->
      <SettingsModal
        :show="showSettings"
        :settings="settings"
        @close="showSettings = false"
        @save="handleSaveSettings"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import VideoInput from './components/VideoInput.vue'
import VideoInfo from './components/VideoInfo.vue'
import DownloadProgress from './components/DownloadProgress.vue'
import HistoryList from './components/HistoryList.vue'
import SettingsModal from './components/SettingsModal.vue'
import { videoApi, downloadApi, settingsApi } from './utils/api'

const POLLING_INTERVAL = 1000
const DOWNLOAD_TIMEOUT = 600000

const isFetching = ref(false)
const isDownloading = ref(false)
const isComplete = ref(false)
const videoInfo = ref(null)
const currentUrl = ref('')
const currentRecordId = ref(null)
const currentStatus = ref('pending')
const selectedQuality = ref('best')

const downloadProgress = ref(0)
const downloadSpeed = ref(0)
const downloadEta = ref(0)
const downloadError = ref('')
const statusText = ref('Ready to download')

const downloads = ref([])
const settings = ref({
  download_path: '',
  proxy_url: '',
  proxy_domains: []
})
const showSettings = ref(false)

let pollInterval = null
let timeoutId = null

const clearTimers = () => {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
  if (timeoutId) {
    clearTimeout(timeoutId)
    timeoutId = null
  }
}

const startDownloadPolling = async (downloadId, onComplete, onError) => {
  clearTimers()
  
  pollInterval = setInterval(async () => {
    try {
      const records = await downloadApi.getDownloads(1)
      if (records.length > 0 && records[0].id === downloadId) {
        const record = records[0]
        
        if (record.status === 'completed') {
          clearTimers()
          onComplete?.()
        } else if (record.status === 'failed') {
          clearTimers()
          onError?.(record.error_msg || 'Download failed')
        }
      }
    } catch (e) {
      console.error('Poll error:', e)
    }
  }, POLLING_INTERVAL)
  
  timeoutId = setTimeout(() => {
    clearTimers()
    if (isDownloading.value) {
      isDownloading.value = false
      downloadError.value = 'Download timeout'
      statusText.value = 'Download timeout'
    }
  }, DOWNLOAD_TIMEOUT)
}

onMounted(() => {
  loadDownloads()
  loadSettings()
})

onUnmounted(() => {
  clearTimers()
})

const loadDownloads = async () => {
  try {
    downloads.value = await downloadApi.getDownloads()
  } catch (error) {
    console.error('Failed to load downloads:', error)
  }
}

const loadSettings = async () => {
  try {
    settings.value = await settingsApi.getSettings()
  } catch (error) {
    console.error('Failed to load settings:', error)
  }
}

const handleFetchInfo = async (url) => {
  isFetching.value = true
  currentUrl.value = url
  
  try {
    const data = await videoApi.getVideoInfo(url)
    videoInfo.value = {
      title: data.title,
      description: data.description,
      duration: data.duration,
      uploader: data.uploader,
      thumbnail: data.thumbnail,
      formats: data.formats
    }
    currentRecordId.value = data.id
    currentStatus.value = data.status
    isComplete.value = data.status === 'completed'
    downloadError.value = ''
    downloadProgress.value = 0
    
    if (data.status === 'completed') {
      statusText.value = 'Already downloaded'
    } else if (data.status === 'failed') {
      statusText.value = 'Previous download failed'
    } else {
      statusText.value = 'Ready to download'
    }
  } catch (error) {
    alert('Failed to fetch video info: ' + error.message)
  } finally {
    isFetching.value = false
  }
}

const handleDownload = async () => {
  if (!currentUrl.value) return
  
  isDownloading.value = true
  isComplete.value = false
  downloadError.value = ''
  downloadProgress.value = 0
  statusText.value = 'Starting download...'
  currentStatus.value = 'downloading'
  
  try {
    const response = await videoApi.startDownload(
      currentUrl.value, 
      selectedQuality.value,
      currentRecordId.value
    )
    const downloadId = response.id
    
    statusText.value = 'Downloading...'
    
    startDownloadPolling(
      downloadId,
      () => {
        isComplete.value = true
        isDownloading.value = false
        currentStatus.value = 'completed'
        statusText.value = 'Download complete!'
        downloadProgress.value = 1
        loadDownloads()
      },
      (errorMsg) => {
        isComplete.value = true
        isDownloading.value = false
        currentStatus.value = 'failed'
        downloadError.value = errorMsg
        statusText.value = 'Download failed'
        loadDownloads()
      }
    )
  } catch (error) {
    isDownloading.value = false
    currentStatus.value = 'failed'
    downloadError.value = error.message
    statusText.value = 'Download failed'
    loadDownloads()
  }
}

const handleRetry = async () => {
  if (!currentRecordId.value) return
  
  isDownloading.value = true
  isComplete.value = false
  downloadError.value = ''
  downloadProgress.value = 0
  statusText.value = 'Retrying download...'
  currentStatus.value = 'downloading'
  
  try {
    const response = await videoApi.retryDownload(currentRecordId.value, selectedQuality.value)
    const downloadId = response.id
    
    statusText.value = 'Downloading...'
    
    startDownloadPolling(
      downloadId,
      () => {
        isComplete.value = true
        isDownloading.value = false
        currentStatus.value = 'completed'
        statusText.value = 'Download complete!'
        downloadProgress.value = 1
        loadDownloads()
      },
      (errorMsg) => {
        isComplete.value = true
        isDownloading.value = false
        currentStatus.value = 'failed'
        downloadError.value = errorMsg
        statusText.value = 'Download failed'
        loadDownloads()
      }
    )
  } catch (error) {
    isDownloading.value = false
    currentStatus.value = 'failed'
    downloadError.value = error.message
    statusText.value = 'Retry failed'
    loadDownloads()
  }
}

const handleRetryFromHistory = async (recordId, quality) => {
  try {
    await videoApi.retryDownload(recordId, quality || 'best')
    await loadDownloads()
  } catch (error) {
    alert('Failed to retry download: ' + error.message)
  }
}

const handleDownloadFromHistory = async (item) => {
  currentUrl.value = item.url
  currentRecordId.value = item.id
  currentStatus.value = item.status
  
  if (item.video_info) {
    videoInfo.value = {
      title: item.video_info.title || item.title,
      description: item.video_info.description,
      duration: item.video_info.duration,
      uploader: item.video_info.uploader,
      thumbnail: item.video_info.thumbnail,
      formats: item.video_info.formats || []
    }
  }
  
  handleDownload()
}

const handleSearch = async (query) => {
  try {
    if (query) {
      downloads.value = await downloadApi.searchDownloads(query)
    } else {
      await loadDownloads()
    }
  } catch (error) {
    console.error('Search failed:', error)
  }
}

const handleClearHistory = async () => {
  if (confirm('Are you sure you want to clear all history?')) {
    try {
      await downloadApi.clearDownloads()
      await loadDownloads()
    } catch (error) {
      console.error('Failed to clear history:', error)
    }
  }
}

const handleDeleteDownload = async (id) => {
  try {
    await downloadApi.deleteDownload(id)
    await loadDownloads()
  } catch (error) {
    console.error('Failed to delete download:', error)
  }
}

const handleSaveSettings = async (newSettings) => {
  try {
    await settingsApi.updateSettings(newSettings)
    settings.value = newSettings
    showSettings.value = false
  } catch (error) {
    alert('Failed to save settings: ' + error.message)
  }
}
</script>
