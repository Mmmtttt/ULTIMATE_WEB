<template>
  <BaseTagManage
    content-type="video"
    :tag-store="tagStore"
    :tag-api="tagApi"
    :home-path="homePath"
  />
</template>

<script setup>
import { onMounted } from 'vue'
import { useTagStore, useModeStore } from '@/stores'
import { tagApi } from '@/api'
import { BaseTagManage } from '@/components/base'

const tagStore = useTagStore()
const modeStore = useModeStore()

const homePath = '/library'

onMounted(() => {
  modeStore.setMode('video')
})
</script>
