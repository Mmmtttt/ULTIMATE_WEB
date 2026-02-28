<template>
  <div class="empty-state" :class="{ 'compact': compact }">
    <div class="empty-icon">{{ icon }}</div>
    <h3 class="empty-title">{{ title }}</h3>
    <p class="empty-description">{{ description }}</p>
    <div v-if="$slots.action" class="empty-action">
      <slot name="action"></slot>
    </div>
  </div>
</template>

<script setup>
defineProps({
  icon: {
    type: String,
    default: '📭'
  },
  title: {
    type: String,
    default: '暂无数据'
  },
  description: {
    type: String,
    default: '当前列表为空'
  },
  compact: {
    type: Boolean,
    default: false
  }
})
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.empty-state.compact {
  padding: 30px 20px;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
  opacity: 0.6;
}

.empty-state.compact .empty-icon {
  font-size: 40px;
  margin-bottom: 12px;
}

.empty-title {
  margin: 0 0 8px;
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.empty-state.compact .empty-title {
  font-size: 16px;
}

.empty-description {
  margin: 0;
  font-size: 14px;
  color: #999;
  max-width: 300px;
  line-height: 1.6;
}

.empty-state.compact .empty-description {
  font-size: 13px;
}

.empty-action {
  margin-top: 20px;
}

.empty-state.compact .empty-action {
  margin-top: 12px;
}
</style>
