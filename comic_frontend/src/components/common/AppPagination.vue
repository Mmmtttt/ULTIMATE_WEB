<template>
  <nav v-if="totalItems > 0" class="app-pagination" aria-label="分页导航">
    <div class="page-summary">
      <span class="summary-pill">第 {{ safePage }} / {{ totalPages }} 页</span>
      <span class="summary-text">显示 {{ range.start }}-{{ range.end }}，共 {{ totalItems }} 条</span>
    </div>
    <van-pagination
      :model-value="safePage"
      :total-items="totalItems"
      :items-per-page="safePageSize"
      :show-page-size="isMobile ? 3 : 5"
      force-ellipses
      prev-text="上一页"
      next-text="下一页"
      @update:model-value="onPageChange"
    />
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useDevice } from '@/composables/useDevice'

const props = defineProps({
  modelValue: {
    type: Number,
    default: 1
  },
  totalItems: {
    type: Number,
    default: 0
  },
  pageSize: {
    type: Number,
    default: 20
  }
})

const emit = defineEmits(['update:modelValue'])
const { isMobile } = useDevice()

const safePageSize = computed(() => {
  const value = Number(props.pageSize)
  if (Number.isFinite(value) && value > 0) {
    return Math.floor(value)
  }
  return 20
})

const totalPages = computed(() => {
  if (props.totalItems <= 0) {
    return 1
  }
  return Math.max(1, Math.ceil(props.totalItems / safePageSize.value))
})

const safePage = computed(() => {
  const page = Number(props.modelValue)
  if (!Number.isFinite(page) || page < 1) {
    return 1
  }
  return Math.min(Math.floor(page), totalPages.value)
})

const range = computed(() => {
  if (props.totalItems <= 0) {
    return { start: 0, end: 0 }
  }
  const start = (safePage.value - 1) * safePageSize.value + 1
  const end = Math.min(props.totalItems, start + safePageSize.value - 1)
  return { start, end }
})

function onPageChange(page) {
  emit('update:modelValue', page)
}
</script>

<style scoped>
.app-pagination {
  margin: 16px auto 10px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--border-soft);
  background: var(--surface-2);
  box-shadow: var(--shadow-xs);
}

.page-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.summary-pill {
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid rgba(25, 137, 250, 0.2);
  background: rgba(25, 137, 250, 0.08);
  color: var(--brand-600);
  font-size: 12px;
  font-weight: 600;
}

.summary-text {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
}

.app-pagination :deep(.van-pagination) {
  justify-content: center;
  gap: 8px;
}

.app-pagination :deep(.van-pagination__item) {
  min-width: 34px;
  height: 34px;
  padding: 0 10px;
  border-radius: 10px;
  border: 1px solid var(--border-soft);
  background: var(--surface-1);
  color: var(--text-primary);
  font-weight: 600;
  transition: all var(--motion-fast) var(--ease-standard);
}

.app-pagination :deep(.van-pagination__item--active) {
  border-color: var(--brand-500);
  background: var(--brand-500);
  color: #fff;
  box-shadow: 0 6px 14px rgba(25, 137, 250, 0.26);
}

.app-pagination :deep(.van-pagination__item--disabled) {
  opacity: 0.45;
}

@media (max-width: 767px) {
  .app-pagination {
    margin: 12px 0 8px;
    padding: 12px 10px;
  }

  .summary-text {
    font-size: 11px;
  }

  .app-pagination :deep(.van-pagination__item) {
    min-width: 32px;
    height: 32px;
    padding: 0 8px;
  }
}
</style>
