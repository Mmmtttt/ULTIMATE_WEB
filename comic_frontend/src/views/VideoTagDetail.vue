<template>
  <BaseTagDetail
    class="desktop-page-shell"
    content-type="video"
    :tag-store="tagStore"
    :tag-api="tagApi"
    home-detail-route="VideoDetail"
    recommendation-detail-route="VideoRecommendationDetail"
  />
</template>

<script setup>
import { useTagStore } from '@/stores'
import { tagApi } from '@/api'
import { BaseTagDetail } from '@/components/base'

const tagStore = useTagStore()
</script>
