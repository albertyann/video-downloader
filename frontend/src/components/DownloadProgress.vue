<template>
  <div class="bg-dark/50 backdrop-blur-sm rounded-xl p-6 border border-gray-700/50">
    <!-- Download Button -->
    <button
      v-if="!isDownloading && !isComplete"
      @click="$emit('download')"
      :disabled="disabled"
      class="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-bold py-4 px-6 rounded-lg transition-colors flex items-center justify-center gap-2 text-lg"
    >
      ⬇️ {{ buttonText }}
    </button>
    
    <!-- Retry Button for Failed Downloads -->
    <button
      v-if="status === 'failed' && !isDownloading"
      @click="$emit('retry')"
      class="w-full bg-orange-600 hover:bg-orange-700 text-white font-bold py-4 px-6 rounded-lg transition-colors flex items-center justify-center gap-2 text-lg mt-3"
    >
      🔄 Retry Download
    </button>
    
    <!-- Progress Bar -->
    <div v-if="isDownloading || isComplete" class="space-y-3">
      <div class="flex justify-between text-sm text-gray-300">
        <span>{{ statusText }}</span>
        <span v-if="progress > 0">{{ Math.round(progress * 100) }}%</span>
      </div>
      
      <div class="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
        <div 
          class="bg-gradient-to-r from-primary to-blue-400 h-full rounded-full transition-all duration-300"
          :style="{ width: `${progress * 100}%` }"
        ></div>
      </div>
      
      <div v-if="speed || eta" class="flex gap-4 text-xs text-gray-400">
        <span v-if="speed">Speed: {{ formatBytes(speed) }}/s</span>
        <span v-if="eta">ETA: {{ formatDuration(eta) }}</span>
      </div>
      
      <!-- Success Message -->
      <div v-if="isComplete && !error" class="text-green-400 text-center py-2">
        ✅ Download complete!
      </div>
      
      <!-- Error Message -->
      <div v-if="error" class="text-red-400 text-center py-2">
        ❌ {{ error }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatBytes, formatDuration } from '../utils/format'

const props = defineProps({
  isDownloading: Boolean,
  isComplete: Boolean,
  disabled: Boolean,
  status: {
    type: String,
    default: 'pending'
  },
  progress: {
    type: Number,
    default: 0
  },
  speed: Number,
  eta: Number,
  error: String,
  statusText: {
    type: String,
    default: 'Downloading...'
  }
})

const emit = defineEmits(['download', 'retry'])

const buttonText = computed(() => {
  switch (props.status) {
    case 'pending':
      return '⬇️ Download Video'
    case 'completed':
      return '✅ Downloaded'
    case 'failed':
      return '❌ Download Failed'
    default:
      return '⬇️ Download Video'
  }
})
</script>
