<template>
  <BaseTrash
    :content-type="contentType"
    :stores="stores"
    :apis="apis"
  />
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useVideoStore, useModeStore, useVideoRecommendationStore } from '@/stores'
import { comicApi, recommendationApi } from '@/api'
import { BaseTrash } from '@/components/base'

const videoStore = useVideoStore()
const videoRecommendationStore = useVideoRecommendationStore()
const modeStore = useModeStore()

const contentType = computed(() => modeStore.isVideoMode ? 'video' : 'comic')

const stores = {
  video: videoStore,
  videoRecommendation: videoRecommendationStore
}

const apis = {
  comic: comicApi,
  recommendation: recommendationApi
}
</script>
