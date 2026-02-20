<template>
  <div v-if="info" class="bg-dark/50 backdrop-blur-sm rounded-xl p-6 border border-gray-700/50">
    <div class="flex gap-6">
      <!-- Thumbnail -->
      <div v-if="info.thumbnail" class="flex-shrink-0">
        <img 
          :src="info.thumbnail" 
          :alt="info.title"
          class="w-48 h-32 object-cover rounded-lg shadow-lg"
        />
      </div>
      
      <!-- Info -->
      <div class="flex-1">
        <h3 class="text-xl font-bold text-white mb-2">
          {{ truncateText(info.title, 60) }}
        </h3>
        
        <div class="flex gap-4 text-sm text-gray-400 mb-4">
          <span v-if="info.duration" class="flex items-center gap-1">
            ⏱️ {{ formatDuration(info.duration) }}
          </span>
          <span v-if="info.uploader" class="flex items-center gap-1">
            👤 {{ info.uploader }}
          </span>
        </div>
        
        <!-- Quality Selection -->
        <div class="flex items-center gap-3">
          <label class="text-sm font-medium text-gray-300">Quality:</label>
          <select 
            :value="modelValue"
            @change="$emit('update:modelValue', $event.target.value)"
            class="bg-darker border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-primary"
          >
            <option v-for="quality in qualities" :key="quality.value" :value="quality.value">
              {{ quality.display }}
            </option>
          </select>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { truncateText, formatDuration } from '../utils/format'

const props = defineProps({
  info: Object,
  modelValue: {
    type: String,
    default: 'best'
  }
})

const emit = defineEmits(['update:modelValue'])

const qualities = computed(() => {
  if (!props.info || !props.info.formats) {
    return [
      { display: 'Best Quality', value: 'best' },
      { display: 'Worst Quality', value: 'worst' }
    ]
  }
  
  const quals = [{ display: 'Best Quality', value: 'best' }]
  const seen = new Set()
  
  for (const fmt of props.info.formats) {
    const res = fmt.resolution
    if (res && res.includes('x')) {
      const height = res.split('x')[1]
      const key = `${height}p`
      if (!seen.has(key)) {
        seen.add(key)
        quals.push({
          display: `${key} (${fmt.ext})`,
          value: key
        })
      }
    }
  }
  
  quals.push({ display: 'Worst Quality', value: 'worst' })
  return quals
})
</script>
