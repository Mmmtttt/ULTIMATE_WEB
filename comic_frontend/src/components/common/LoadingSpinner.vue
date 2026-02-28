<template>
  <div class="loading-spinner" :class="[`size-${size}`, { 'inline': inline }]">
    <div class="spinner-container">
      <div class="spinner-ring"></div>
      <div class="spinner-ring"></div>
      <div class="spinner-ring"></div>
    </div>
    <span v-if="text" class="spinner-text">{{ text }}</span>
  </div>
</template>

<script setup>
defineProps({
  size: {
    type: String,
    default: 'medium', // small, medium, large
    validator: (value) => ['small', 'medium', 'large'].includes(value)
  },
  text: {
    type: String,
    default: ''
  },
  inline: {
    type: Boolean,
    default: false
  }
})
</script>

<style scoped>
.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.loading-spinner.inline {
  display: inline-flex;
  flex-direction: row;
  gap: 8px;
}

.spinner-container {
  position: relative;
  display: inline-block;
}

.spinner-ring {
  position: absolute;
  border-radius: 50%;
  border: 3px solid transparent;
  border-top-color: #07c160;
  animation: spin 1s linear infinite;
}

.spinner-ring:nth-child(1) {
  animation-duration: 1s;
}

.spinner-ring:nth-child(2) {
  animation-duration: 0.8s;
  animation-direction: reverse;
  opacity: 0.7;
}

.spinner-ring:nth-child(3) {
  animation-duration: 0.6s;
  opacity: 0.4;
}

/* 尺寸 */
.size-small .spinner-container {
  width: 24px;
  height: 24px;
}

.size-small .spinner-ring {
  width: 24px;
  height: 24px;
  border-width: 2px;
}

.size-medium .spinner-container {
  width: 40px;
  height: 40px;
}

.size-medium .spinner-ring {
  width: 40px;
  height: 40px;
  border-width: 3px;
}

.size-large .spinner-container {
  width: 60px;
  height: 60px;
}

.size-large .spinner-ring {
  width: 60px;
  height: 60px;
  border-width: 4px;
}

.spinner-text {
  font-size: 14px;
  color: #666;
}

.size-small .spinner-text {
  font-size: 12px;
}

.size-large .spinner-text {
  font-size: 16px;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}
</style>
