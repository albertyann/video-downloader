<template>
  <div class="bg-dark/50 backdrop-blur-sm rounded-xl p-6 border border-gray-700/50">
    <label class="block text-sm font-medium text-gray-300 mb-2">
      Video URL
    </label>
    <div class="flex gap-3">
      <input
        v-model="url"
        type="text"
        placeholder="Enter video URL here..."
        class="flex-1 bg-darker border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors"
        @keyup.enter="handleFetch"
      />
      <button
        @click="handleFetch"
        :disabled="loading || !url"
        class="bg-primary hover:bg-blue-600 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-medium px-6 py-3 rounded-lg transition-colors flex items-center gap-2"
      >
        <span v-if="loading" class="animate-spin">⌛</span>
        <span>{{ loading ? 'Loading...' : 'Fetch Info' }}</span>
      </button>
    </div>
    <p v-if="errorMessage" class="text-red-400 text-sm mt-2">{{ errorMessage }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  loading: Boolean
})

const emit = defineEmits(['fetch'])

const url = ref('')
const errorMessage = ref('')

const SUPPORTED_DOMAINS = [
  'youtube.com',
  'youtu.be',
  'bilibili.com',
  'b23.tv',
  'vimeo.com',
  'dailymotion.com',
  'tiktok.com'
]

const validateUrl = (urlString) => {
  errorMessage.value = ''
  
  if (!urlString || !urlString.trim()) {
    errorMessage.value = '请输入视频 URL'
    return false
  }
  
  let trimmedUrl = urlString.trim()
  
  try {
    const urlObj = new URL(trimmedUrl)
    
    if (!['http:', 'https:'].includes(urlObj.protocol)) {
      errorMessage.value = 'URL 必须使用 http 或 https 协议'
      return false
    }
    
    if (!urlObj.hostname) {
      errorMessage.value = '无效的 URL 格式'
      return false
    }
    
    const hostname = urlObj.hostname.toLowerCase().replace('www.', '')
    const isSupported = SUPPORTED_DOMAINS.some(domain => hostname.includes(domain))
    
    if (!isSupported) {
      console.warn('未验证的域名:', hostname)
    }
    
    return true
  } catch (e) {
    errorMessage.value = '请输入有效的 URL'
    return false
  }
}

const handleFetch = () => {
  if (!validateUrl(url.value)) {
    return
  }
  
  emit('fetch', url.value.trim())
}
</script>
