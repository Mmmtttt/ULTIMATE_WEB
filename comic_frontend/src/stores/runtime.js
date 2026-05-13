import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { configApi } from '@/api'

function defaultRuntimePayload() {
  return {
    runtime_profile: '',
    third_party_enabled: false,
    mobile_core: false,
  }
}

export const useRuntimeStore = defineStore('runtime', () => {
  const runtime = ref(defaultRuntimePayload())
  const loaded = ref(false)
  const loading = ref(false)

  const runtimeProfile = computed(() => String(runtime.value.runtime_profile || '').trim().toLowerCase())
  const thirdPartyEnabled = computed(() => Boolean(runtime.value.third_party_enabled))
  const isMobileCore = computed(() => Boolean(runtime.value.mobile_core))
  const supportsLocalVideoThumbnailBatch = computed(() => !isMobileCore.value)

  async function fetchRuntime(force = false) {
    if (loading.value) {
      return runtime.value
    }
    if (loaded.value && !force) {
      return runtime.value
    }

    loading.value = true
    try {
      const response = await configApi.getSystemConfig()
      const payload = response?.code === 200
        ? { ...defaultRuntimePayload(), ...(response.data?.runtime || {}) }
        : defaultRuntimePayload()
      runtime.value = payload
      loaded.value = true
      return runtime.value
    } catch (_error) {
      runtime.value = defaultRuntimePayload()
      loaded.value = true
      return runtime.value
    } finally {
      loading.value = false
    }
  }

  return {
    runtime,
    loaded,
    loading,
    runtimeProfile,
    thirdPartyEnabled,
    isMobileCore,
    supportsLocalVideoThumbnailBatch,
    fetchRuntime,
  }
})
