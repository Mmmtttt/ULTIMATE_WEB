<template>
  <span
    class="tag-badge"
    :class="[
      `size-${size}`,
      `type-${type}`,
      {
        'tag-clickable': clickable,
        'tag-selected': selected,
        'tag-closable': closable
      }
    ]"
    :style="customStyle"
    @click="handleClick"
  >
    <span class="tag-text">{{ displayName }}</span>
    <span v-if="showCount && count > 0" class="tag-count">{{ count }}</span>
    <button
      v-if="closable"
      class="tag-close"
      @click.stop="handleClose"
    >
      ✕
    </button>
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  tag: {
    type: [Object, String],
    required: true
  },
  size: {
    type: String,
    default: 'medium', // small, medium, large
    validator: (value) => ['small', 'medium', 'large'].includes(value)
  },
  type: {
    type: String,
    default: 'default', // default, primary, success, warning, danger
    validator: (value) => ['default', 'primary', 'success', 'warning', 'danger'].includes(value)
  },
  clickable: {
    type: Boolean,
    default: false
  },
  selected: {
    type: Boolean,
    default: false
  },
  closable: {
    type: Boolean,
    default: false
  },
  showCount: {
    type: Boolean,
    default: false
  },
  count: {
    type: Number,
    default: 0
  },
  color: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['click', 'close'])

// 显示名称
const displayName = computed(() => {
  if (typeof props.tag === 'string') {
    return props.tag
  }
  return props.tag?.name || props.tag?.id || ''
})

// 自定义样式
const customStyle = computed(() => {
  if (props.color) {
    return {
      backgroundColor: props.color + '20', // 20% 透明度
      borderColor: props.color,
      color: props.color
    }
  }
  return {}
})

// 处理点击
function handleClick() {
  if (props.clickable) {
    emit('click', props.tag)
  }
}

// 处理关闭
function handleClose() {
  emit('close', props.tag)
}
</script>

<style scoped>
.tag-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border-radius: 4px;
  font-weight: 500;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}

/* 尺寸 */
.size-small {
  padding: 2px 8px;
  font-size: 12px;
  border-radius: 10px;
}

.size-medium {
  padding: 4px 12px;
  font-size: 13px;
  border-radius: 12px;
}

.size-large {
  padding: 6px 16px;
  font-size: 14px;
  border-radius: 14px;
}

/* 类型 */
.type-default {
  background: #f0f0f0;
  color: #666;
}

.type-primary {
  background: rgba(7, 193, 96, 0.1);
  color: #07c160;
  border-color: rgba(7, 193, 96, 0.3);
}

.type-success {
  background: rgba(7, 193, 96, 0.1);
  color: #07c160;
  border-color: rgba(7, 193, 96, 0.3);
}

.type-warning {
  background: rgba(255, 170, 0, 0.1);
  color: #ffaa00;
  border-color: rgba(255, 170, 0, 0.3);
}

.type-danger {
  background: rgba(255, 77, 79, 0.1);
  color: #ff4d4f;
  border-color: rgba(255, 77, 79, 0.3);
}

/* 可点击 */
.tag-clickable {
  cursor: pointer;
}

.tag-clickable:hover {
  opacity: 0.8;
  transform: translateY(-1px);
}

/* 选中状态 */
.tag-selected {
  background: #07c160 !important;
  color: #fff !important;
  border-color: #07c160 !important;
}

/* 数量 */
.tag-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 9px;
  font-size: 11px;
  font-weight: 600;
}

.tag-selected .tag-count {
  background: rgba(255, 255, 255, 0.3);
}

/* 关闭按钮 */
.tag-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  margin-left: 2px;
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
  font-size: 12px;
  cursor: pointer;
  border-radius: 50%;
  opacity: 0.6;
  transition: all 0.2s;
}

.tag-close:hover {
  opacity: 1;
  background: rgba(0, 0, 0, 0.1);
}

.tag-selected .tag-close:hover {
  background: rgba(255, 255, 255, 0.3);
}
</style>
