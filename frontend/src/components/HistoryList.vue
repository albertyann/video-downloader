<template>
  <div class="bg-dark/50 backdrop-blur-sm rounded-xl border border-gray-700/50 overflow-hidden">
    <!-- Header -->
    <div class="p-4 border-b border-gray-700/50 flex items-center justify-between">
      <h3 class="text-lg font-bold text-white">📜 Download History</h3>
      
      <div class="flex gap-2">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search..."
          class="bg-darker border border-gray-600 rounded-lg px-3 py-1 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-primary"
          @keyup.enter="handleSearch"
        />
        
        <button
          @click="handleSearch"
          class="bg-secondary hover:bg-gray-600 text-white text-sm px-3 py-1 rounded-lg transition-colors"
        >
          Search
        </button>
        
        <button
          @click="$emit('clear')"
          class="bg-red-600/80 hover:bg-red-700 text-white text-sm px-3 py-1 rounded-lg transition-colors"
        >
          Clear All
        </button>
      </div>
    </div>
    
    <!-- List -->
    <div class="max-h-96 overflow-y-auto">
      <div v-if="downloads.length === 0" class="p-8 text-center text-gray-400">
        No download history yet
      </div>
      
      <div
        v-for="item in downloads"
        :key="item.id"
        class="p-4 border-b border-gray-700/30 hover:bg-white/5 transition-colors"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <h4 class="font-medium text-white mb-1">
              {{ truncateText(item.title, 50) }}
            </h4>
            
            <div class="flex gap-3 text-xs text-gray-400">
              <span>{{ formatDate(item.created_at) }}</span>
              <span 
                :class="{
                  'text-green-400': item.status === 'completed',
                  'text-red-400': item.status === 'failed',
                  'text-yellow-400': item.status === 'downloading',
                  'text-blue-400': item.status === 'pending'
                }"
              >
                ● {{ item.status }}
              </span>
              <span v-if="item.quality">{{ item.quality }}</span>
              <span v-if="item.file_size">{{ formatBytes(item.file_size) }}</span>
            </div>
            
            <div v-if="item.error_msg" class="text-xs text-red-400 mt-1">
              {{ item.error_msg }}
            </div>
          </div>
          
          <div class="flex gap-2 ml-4">
            <!-- Retry button for failed/pending -->
            <button
              v-if="item.status === 'failed' || item.status === 'pending'"
              @click="$emit('retry', item.id, item.quality)"
              class="bg-orange-600/80 hover:bg-orange-700 text-white text-xs px-3 py-1 rounded transition-colors"
            >
              🔄 Retry
            </button>
            
            <!-- Download button for pending -->
            <button
              v-if="item.status === 'pending'"
              @click="$emit('download-item', item)"
              class="bg-green-600/80 hover:bg-green-700 text-white text-xs px-3 py-1 rounded transition-colors"
            >
              ⬇️ Download
            </button>
            
            <button
              @click="$emit('delete', item.id)"
              class="text-gray-500 hover:text-red-400 transition-colors"
            >
              🗑️
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { truncateText, formatBytes } from '../utils/format'

defineProps({
  downloads: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['search', 'clear', 'delete', 'retry', 'download-item'])

const searchQuery = ref('')

const handleSearch = () => {
  emit('search', searchQuery.value)
}

const formatDate = (dateString) => {
  const date = new Date(dateString)
  return date.toLocaleString()
}
</script>
