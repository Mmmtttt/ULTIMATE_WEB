<template>
  <div class="reader-toolbar" :class="{ 'toolbar-hidden': !visible }">
    <!-- 顶部工具栏 -->
    <div class="toolbar-top">
      <div class="toolbar-left">
        <button class="btn-icon" @click="$emit('back')">
          <span class="icon">←</span>
        </button>
        <span class="comic-title">{{ title }}</span>
      </div>
      
      <div class="toolbar-right">
        <button class="btn-icon" @click="$emit('toggle-settings')">
          <span class="icon">⚙</span>
        </button>
      </div>
    </div>
    
    <!-- 底部工具栏 -->
    <div class="toolbar-bottom">
      <div class="toolbar-controls">
        <button 
          class="btn-control" 
          :disabled="!canGoPrev"
          @click="$emit('prev')"
        >
          <span class="icon">‹</span>
          <span>上一页</span>
        </button>
        
        <div class="page-info">
          <span class="current-page">{{ currentPage }}</span>
          <span class="page-separator">/</span>
          <span class="total-page">{{ totalPage }}</span>
        </div>
        
        <button 
          class="btn-control" 
          :disabled="!canGoNext"
          @click="$emit('next')"
        >
          <span>下一页</span>
          <span class="icon">›</span>
        </button>
      </div>
      
      <div class="toolbar-zoom">
        <button class="btn-icon" @click="$emit('zoom-out')">
          <span class="icon">−</span>
        </button>
        <span class="zoom-level">{{ scalePercent }}%</span>
        <button class="btn-icon" @click="$emit('zoom-in')">
          <span class="icon">+</span>
        </button>
        <button class="btn-icon" @click="$emit('zoom-reset')">
          <span class="icon">⟲</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  visible: {
    type: Boolean,
    default: true
  },
  title: {
    type: String,
    default: ''
  },
  currentPage: {
    type: Number,
    default: 1
  },
  totalPage: {
    type: Number,
    default: 1
  },
  canGoPrev: {
    type: Boolean,
    default: false
  },
  canGoNext: {
    type: Boolean,
    default: false
  },
  scalePercent: {
    type: Number,
    default: 100
  }
})

defineEmits([
  'back',
  'toggle-settings',
  'prev',
  'next',
  'zoom-in',
  'zoom-out',
  'zoom-reset'
])
</script>

<style scoped>
.reader-toolbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 100;
  transition: opacity 0.3s ease;
}

.reader-toolbar.toolbar-hidden {
  opacity: 0;
}

.toolbar-top,
.toolbar-bottom {
  position: absolute;
  left: 0;
  right: 0;
  padding: 10px 15px;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  pointer-events: auto;
}

.toolbar-top {
  top: 0;
}

.toolbar-bottom {
  bottom: 0;
  flex-direction: column;
  gap: 10px;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.comic-title {
  color: #fff;
  font-size: 16px;
  font-weight: 500;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.btn-icon {
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.btn-icon:hover {
  background: rgba(255, 255, 255, 0.2);
}

.btn-icon .icon {
  font-size: 20px;
}

.toolbar-controls {
  display: flex;
  align-items: center;
  gap: 20px;
}

.btn-control {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  cursor: pointer;
  transition: background 0.2s;
  font-size: 14px;
}

.btn-control:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.2);
}

.btn-control:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-control .icon {
  font-size: 18px;
}

.page-info {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #fff;
  font-size: 16px;
}

.current-page {
  font-weight: 600;
  color: #07c160;
}

.page-separator {
  opacity: 0.6;
}

.total-page {
  opacity: 0.8;
}

.toolbar-zoom {
  display: flex;
  align-items: center;
  gap: 10px;
}

.zoom-level {
  color: #fff;
  font-size: 14px;
  min-width: 50px;
  text-align: center;
}

@media (max-width: 768px) {
  .comic-title {
    max-width: 150px;
    font-size: 14px;
  }
  
  .btn-control span:not(.icon) {
    display: none;
  }
  
  .toolbar-controls {
    gap: 10px;
  }
}
</style>
