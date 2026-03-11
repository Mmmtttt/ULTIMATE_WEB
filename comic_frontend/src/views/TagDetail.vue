<template>
  <BaseTagDetail
    content-type="comic"
    :tag-store="tagStore"
    :tag-api="tagApi"
    home-detail-route="ComicDetail"
    recommendation-detail-route="RecommendationDetail"
  />
</template>

<script setup>
import { useTagStore } from '@/stores'
import { tagApi } from '@/api'
import { BaseTagDetail } from '@/components/base'

const tagStore = useTagStore()
</script>
