<template>
  <div class="reader-settings" :class="{ 'settings-visible': visible }">
    <div class="settings-overlay" @click="$emit('close')"></div>
    
    <div class="settings-panel">
      <div class="settings-header">
        <h3>阅读设置</h3>
        <button class="btn-close" @click="$emit('close')">✕</button>
      </div>
      
      <div class="settings-content">
        <!-- 翻页模式 -->
        <div class="setting-item">
          <label class="setting-label">翻页模式</label>
          <div class="setting-options">
            <button
              v-for="mode in pageModes"
              :key="mode.value"
              class="option-btn"
              :class="{ active: currentMode === mode.value }"
              @click="$emit('update:mode', mode.value)"
            >
              <span class="option-icon">{{ mode.icon }}</span>
              <span class="option-text">{{ mode.label }}</span>
            </button>
          </div>
        </div>
        
        <!-- 背景色 -->
        <div class="setting-item">
          <label class="setting-label">背景颜色</label>
          <div class="setting-options">
            <button
              v-for="bg in backgrounds"
              :key="bg.value"
              class="color-btn"
              :class="{ active: currentBackground === bg.value }"
              :style="{ backgroundColor: bg.color }"
              @click="$emit('update:background', bg.value)"
            >
              <span v-if="currentBackground === bg.value" class="check">✓</span>
            </button>
          </div>
        </div>
        
        <!-- 预加载数量 -->
        <div class="setting-item">
          <label class="setting-label">
            预加载数量
            <span class="label-hint">（同时加载的图片数）</span>
          </label>
          <div class="preload-control">
            <button 
              class="btn-adjust" 
              :disabled="preloadNum <= minPreload"
              @click="$emit('update:preloadNum', preloadNum - 1)"
            >−</button>
            <span class="preload-value">{{ preloadNum }}</span>
            <button 
              class="btn-adjust" 
              :disabled="preloadNum >= maxPreload"
              @click="$emit('update:preloadNum', preloadNum + 1)"
            >+</button>
          </div>
        </div>
        
        <!-- 自动隐藏工具栏 -->
        <div class="setting-item setting-toggle">
          <label class="setting-label">自动隐藏工具栏</label>
          <label class="toggle-switch">
            <input
              type="checkbox"
              :checked="autoHideToolbar"
              @change="$emit('update:autoHideToolbar', $event.target.checked)"
            />
            <span class="toggle-slider"></span>
          </label>
        </div>
        
        <!-- 显示页码 -->
        <div class="setting-item setting-toggle">
          <label class="setting-label">显示页码</label>
          <label class="toggle-switch">
            <input
              type="checkbox"
              :checked="showPageNumber"
              @change="$emit('update:showPageNumber', $event.target.checked)"
            />
            <span class="toggle-slider"></span>
          </label>
        </div>
      </div>
      
      <div class="settings-footer">
        <button class="btn-reset" @click="$emit('reset')">恢复默认</button>
        <button class="btn-confirm" @click="$emit('close')">确定</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { PAGE_MODE, BACKGROUND, PRELOAD_RANGE } from '@/utils'

defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  currentMode: {
    type: String,
    default: PAGE_MODE.LEFT_RIGHT
  },
  currentBackground: {
    type: String,
    default: BACKGROUND.WHITE
  },
  preloadNum: {
    type: Number,
    default: 5
  },
  autoHideToolbar: {
    type: Boolean,
    default: true
  },
  showPageNumber: {
    type: Boolean,
    default: true
  }
})

defineEmits([
  'close',
  'update:mode',
  'update:background',
  'update:preloadNum',
  'update:autoHideToolbar',
  'update:showPageNumber',
  'reset'
])

// 翻页模式选项
const pageModes = [
  { value: PAGE_MODE.LEFT_RIGHT, label: '左右翻页', icon: '↔' },
  { value: PAGE_MODE.UP_DOWN, label: '上下翻页', icon: '↕' }
]

// 背景色选项
const backgrounds = [
  { value: BACKGROUND.WHITE, color: '#ffffff', label: '白色' },
  { value: BACKGROUND.DARK, color: '#1a1a1a', label: '深色' },
  { value: BACKGROUND.EYE_PROTECTION, color: '#c7edcc', label: '护眼' }
]

// 预加载范围
const minPreload = PRELOAD_RANGE.MIN
const maxPreload = PRELOAD_RANGE.MAX
</script>

<style scoped>
.reader-settings {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s ease;
}

.reader-settings.settings-visible {
  opacity: 1;
  pointer-events: auto;
}

.settings-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
}

.settings-panel {
  position: relative;
  width: 90%;
  max-width: 400px;
  max-height: 80vh;
  background: #fff;
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
  border-bottom: 1px solid #eee;
}

.settings-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.btn-close {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  font-size: 18px;
  color: #666;
  transition: background 0.2s;
}

.btn-close:hover {
  background: #f5f5f5;
}

.settings-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.setting-item {
  margin-bottom: 24px;
}

.setting-item:last-child {
  margin-bottom: 0;
}

.setting-label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #333;
  margin-bottom: 12px;
}

.label-hint {
  font-weight: normal;
  color: #999;
  font-size: 12px;
  margin-left: 5px;
}

.setting-options {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.option-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border: 2px solid #e0e0e0;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
}

.option-btn:hover {
  border-color: #07c160;
}

.option-btn.active {
  border-color: #07c160;
  background: rgba(7, 193, 96, 0.1);
  color: #07c160;
}

.option-icon {
  font-size: 16px;
}

.color-btn {
  width: 48px;
  height: 48px;
  border: 3px solid transparent;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.color-btn:hover {
  transform: scale(1.1);
}

.color-btn.active {
  border-color: #07c160;
}

.check {
  color: #07c160;
  font-weight: bold;
  font-size: 20px;
}

.preload-control {
  display: flex;
  align-items: center;
  gap: 15px;
}

.btn-adjust {
  width: 40px;
  height: 40px;
  border: 2px solid #e0e0e0;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  font-size: 20px;
  font-weight: 500;
  transition: all 0.2s;
}

.btn-adjust:hover:not(:disabled) {
  border-color: #07c160;
  color: #07c160;
}

.btn-adjust:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.preload-value {
  font-size: 20px;
  font-weight: 600;
  min-width: 40px;
  text-align: center;
}

.setting-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.toggle-switch {
  position: relative;
  width: 50px;
  height: 28px;
  cursor: pointer;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: #ccc;
  border-radius: 28px;
  transition: background 0.3s;
}

.toggle-slider::before {
  content: '';
  position: absolute;
  height: 22px;
  width: 22px;
  left: 3px;
  bottom: 3px;
  background: #fff;
  border-radius: 50%;
  transition: transform 0.3s;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.toggle-switch input:checked + .toggle-slider {
  background: #07c160;
}

.toggle-switch input:checked + .toggle-slider::before {
  transform: translateX(22px);
}

.settings-footer {
  display: flex;
  gap: 10px;
  padding: 20px;
  border-top: 1px solid #eee;
}

.btn-reset,
.btn-confirm {
  flex: 1;
  padding: 12px 20px;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-reset {
  border: 2px solid #e0e0e0;
  background: #fff;
  color: #666;
}

.btn-reset:hover {
  border-color: #999;
  color: #333;
}

.btn-confirm {
  border: none;
  background: #07c160;
  color: #fff;
}

.btn-confirm:hover {
  background: #06ad56;
}

@media (max-width: 768px) {
  .settings-panel {
    width: 95%;
    max-height: 90vh;
  }
  
  .settings-content {
    padding: 15px;
  }
  
  .setting-options {
    gap: 8px;
  }
  
  .option-btn {
    padding: 8px 12px;
    font-size: 13px;
  }
}
</style>
