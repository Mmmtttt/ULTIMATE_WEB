<template>
  <div class="reader-progress" :class="{ 'progress-hidden': !visible }">
    <div class="progress-slider">
      <input
        type="range"
        :min="1"
        :max="totalPage"
        :value="currentPage"
        class="progress-input"
        @input="handleInput"
        @change="handleChange"
      />
      <div class="progress-track">
        <div 
          class="progress-fill" 
          :style="{ width: progressPercent + '%' }"
        ></div>
      </div>
    </div>
    
    <div class="progress-info">
      <span class="progress-text">{{ progressText }}</span>
      <span class="progress-percent">{{ progressPercent }}%</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: true
  },
  currentPage: {
    type: Number,
    default: 1
  },
  totalPage: {
    type: Number,
    default: 1
  }
})

const emit = defineEmits(['update:currentPage', 'change'])

// 进度百分比
const progressPercent = computed(() => {
  if (props.totalPage <= 0) return 0
  return Math.round((props.currentPage / props.totalPage) * 100)
})

// 进度文本
const progressText = computed(() => {
  return `${props.currentPage} / ${props.totalPage}`
})

// 处理输入（实时更新，但不触发跳转）
function handleInput(event) {
  const page = parseInt(event.target.value)
  emit('update:currentPage', page)
}

// 处理变化（触发跳转）
function handleChange(event) {
  const page = parseInt(event.target.value)
  emit('change', page)
}
</script>

<style scoped>
.reader-progress {
  padding: 15px 20px;
  background: rgba(0, 0, 0, 0.9);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  transition: opacity 0.3s ease;
}

.reader-progress.progress-hidden {
  opacity: 0;
  pointer-events: none;
}

.progress-slider {
  position: relative;
  height: 30px;
  display: flex;
  align-items: center;
}

.progress-input {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
  z-index: 2;
}

.progress-track {
  width: 100%;
  height: 6px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #07c160, #10b981);
  border-radius: 3px;
  transition: width 0.1s ease;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
  color: #fff;
  font-size: 14px;
}

.progress-text {
  font-weight: 500;
}

.progress-percent {
  color: #07c160;
  font-weight: 600;
}

/* 自定义滑块样式 */
.progress-input::-webkit-slider-thumb {
  appearance: none;
  width: 20px;
  height: 20px;
  background: #07c160;
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(7, 193, 96, 0.4);
}

.progress-input::-moz-range-thumb {
  width: 20px;
  height: 20px;
  background: #07c160;
  border-radius: 50%;
  cursor: pointer;
  border: none;
  box-shadow: 0 2px 6px rgba(7, 193, 96, 0.4);
}

@media (max-width: 768px) {
  .reader-progress {
    padding: 10px 15px;
  }
  
  .progress-info {
    font-size: 12px;
  }
}
</style>
