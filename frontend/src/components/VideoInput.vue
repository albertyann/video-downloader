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
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  loading: Boolean
})

const emit = defineEmits(['fetch'])

const url = ref('')

const handleFetch = () => {
  if (url.value.trim()) {
    emit('fetch', url.value.trim())
  }
}
</script>
