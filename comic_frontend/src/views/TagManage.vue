<template>
  <BaseTagManage
    content-type="comic"
    :tag-store="tagStore"
    :tag-api="tagApi"
    home-path="/"
  />
</template>

<script setup>
import { useTagStore } from '@/stores'
import { tagApi } from '@/api'
import { BaseTagManage } from '@/components/base'

const tagStore = useTagStore()
</script>
