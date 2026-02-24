<template>
  <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <!-- Backdrop -->
    <div 
      class="absolute inset-0 bg-black/70 backdrop-blur-sm"
      @click="$emit('close')"
    ></div>
    
    <!-- Modal -->
    <div class="relative bg-dark rounded-xl border border-gray-700/50 w-full max-w-lg shadow-2xl">
      <!-- Header -->
      <div class="p-6 border-b border-gray-700/50">
        <h2 class="text-xl font-bold text-white">Settings</h2>
      </div>
      
      <!-- Content -->
      <div class="p-6 space-y-6">
        <!-- Download Path -->
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-2">
            Download Path
          </label>
          <div class="flex gap-2">
            <input
              v-model="localSettings.download_path"
              type="text"
              class="flex-1 bg-darker border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-primary"
            />
          </div>
        </div>
        
        <!-- Proxy URL -->
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-2">
            Proxy URL
          </label>
          <input
            v-model="localSettings.proxy_url"
            type="text"
            :placeholder="localSettings.default_proxy_url || 'http://proxy:port or socks5://proxy:port'"
            class="w-full bg-darker border border-gray-600 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-primary"
          />
          <p v-if="localSettings.default_proxy_url" class="text-xs text-gray-500 mt-1">
            Default: {{ localSettings.default_proxy_url }}
          </p>
        </div>
        
        <!-- Proxy Domains -->
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-2">
            Proxy Domains (one per line)
          </label>
          <textarea
            v-model="proxyDomainsText"
            rows="4"
            class="w-full bg-darker border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-primary resize-none"
          ></textarea>
          <p class="text-xs text-gray-500 mt-1">
            These domains will use the proxy
            <span v-if="localSettings.default_proxy_domains?.length">
              (Default: {{ localSettings.default_proxy_domains.join(', ') }})
            </span>
          </p>
        </div>
      </div>
      
      <!-- Footer -->
      <div class="p-6 border-t border-gray-700/50 flex justify-end gap-3">
        <button
          @click="$emit('close')"
          class="px-4 py-2 text-gray-300 hover:text-white transition-colors"
        >
          Cancel
        </button>
        
        <button
          @click="saveSettings"
          class="bg-primary hover:bg-blue-600 text-white font-medium px-6 py-2 rounded-lg transition-colors"
        >
          Save
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  show: Boolean,
  settings: Object
})

const emit = defineEmits(['close', 'save'])

const localSettings = ref({
  download_path: '',
  proxy_url: '',
  proxy_domains: [],
  default_proxy_url: '',
  default_proxy_domains: []
})

const proxyDomainsText = ref('')

watch(() => props.settings, (newSettings) => {
  if (newSettings) {
    localSettings.value = { ...newSettings }
    proxyDomainsText.value = (newSettings.proxy_domains || []).join('\n')
  }
}, { immediate: true })

const saveSettings = () => {
  const domains = proxyDomainsText.value
    .split('\n')
    .map(d => d.trim())
    .filter(d => d)
  
  emit('save', {
    ...localSettings.value,
    proxy_domains: domains
  })
}
</script>
