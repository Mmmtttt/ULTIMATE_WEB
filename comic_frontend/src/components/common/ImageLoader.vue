<template>
  <div class="image-loader" :class="{ 'loading': isLoading, 'error': hasError }">
    <!-- 加载占位符 -->
    <div v-if="isLoading" class="image-placeholder">
      <LoadingSpinner size="small" />
    </div>
    
    <!-- 错误占位符 -->
    <div v-else-if="hasError" class="image-error">
      <span class="error-icon">⚠</span>
      <span class="error-text">加载失败</span>
    </div>
    
    <!-- 实际图片 -->
    <img
      v-show="!isLoading && !hasError"
      :src="src"
      :alt="alt"
      class="image-content"
      @load="handleLoad"
      @error="handleError"
    />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import LoadingSpinner from './LoadingSpinner.vue'

const props = defineProps({
  src: {
    type: String,
    required: true
  },
  alt: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['load', 'error'])

const isLoading = ref(true)
const hasError = ref(false)

// 监听 src 变化，重置状态
watch(() => props.src, () => {
  isLoading.value = true
  hasError.value = false
})

function handleLoad() {
  isLoading.value = false
  hasError.value = false
  emit('load')
}

function handleError() {
  isLoading.value = false
  hasError.value = true
  emit('error')
}
</script>

<style scoped>
.image-loader {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
}

.image-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
}

.image-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #999;
}

.error-icon {
  font-size: 24px;
}

.error-text {
  font-size: 12px;
}

.image-content {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
