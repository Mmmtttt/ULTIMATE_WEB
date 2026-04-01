<template>
  <nav v-if="totalItems > 0" class="app-pagination" aria-label="分页导航">
    <div class="summary-row">
      <div class="summary-main">第 {{ safePage }} / {{ totalPages }} 页</div>
      <button type="button" class="jump-trigger" @click="openJumpPopup">跳转</button>
    </div>

    <div class="summary-sub">显示 {{ range.start }}-{{ range.end }}，共 {{ totalItems }} 条</div>

    <div class="pager-row">
      <button
        type="button"
        class="pager-btn edge-btn"
        :disabled="safePage <= 1"
        aria-label="首页"
        @click="goToPage(1)"
      >
        «
      </button>

      <button
        type="button"
        class="pager-btn nav-btn"
        :disabled="safePage <= 1"
        aria-label="上一页"
        @click="goToPage(safePage - 1)"
      >
        <van-icon name="arrow-left" />
      </button>

      <button
        v-for="item in pageItems"
        :key="item.key"
        type="button"
        class="pager-btn"
        :class="{
          active: item.type === 'page' && item.value === safePage,
          ellipsis: item.type === 'ellipsis'
        }"
        :aria-current="item.type === 'page' && item.value === safePage ? 'page' : undefined"
        :aria-label="item.type === 'page' ? `第 ${item.value} 页` : undefined"
        @click="handleItemClick(item)"
      >
        <template v-if="item.type === 'page'">{{ item.value }}</template>
        <template v-else>…</template>
      </button>

      <button
        type="button"
        class="pager-btn nav-btn"
        :disabled="safePage >= totalPages"
        aria-label="下一页"
        @click="goToPage(safePage + 1)"
      >
        <van-icon name="arrow" />
      </button>

      <button
        type="button"
        class="pager-btn edge-btn"
        :disabled="safePage >= totalPages"
        aria-label="末页"
        @click="goToPage(totalPages)"
      >
        »
      </button>
    </div>

    <van-popup v-model:show="showJumpPopup" position="bottom" round class="jump-popup">
      <div class="jump-panel">
        <div class="jump-title">跳转到指定页</div>
        <div class="jump-hint">当前第 {{ safePage }} 页，共 {{ totalPages }} 页</div>

        <van-field
          v-model="jumpInput"
          type="number"
          label="页码"
          :placeholder="`请输入 1-${totalPages}`"
          input-align="center"
          @keyup.enter="confirmJump"
        />

        <div class="jump-actions">
          <van-button block plain @click="showJumpPopup = false">取消</van-button>
          <van-button block type="primary" @click="confirmJump">跳转</van-button>
        </div>
      </div>
    </van-popup>
  </nav>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { showToast } from 'vant'
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

const showJumpPopup = ref(false)
const jumpInput = ref('')

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

const pageItems = computed(() => {
  const total = totalPages.value
  const current = safePage.value

  if (total <= 7) {
    return Array.from({ length: total }, (_, index) => ({
      key: `p-${index + 1}`,
      type: 'page',
      value: index + 1
    }))
  }

  const sibling = isMobile.value ? 1 : 2
  const items = [{ key: 'p-1', type: 'page', value: 1 }]

  const left = Math.max(2, current - sibling)
  const right = Math.min(total - 1, current + sibling)

  if (left > 2) {
    items.push({ key: 'ellipsis-left', type: 'ellipsis', value: 'left' })
  }

  for (let page = left; page <= right; page += 1) {
    items.push({ key: `p-${page}`, type: 'page', value: page })
  }

  if (right < total - 1) {
    items.push({ key: 'ellipsis-right', type: 'ellipsis', value: 'right' })
  }

  items.push({ key: `p-${total}`, type: 'page', value: total })
  return items
})

watch(showJumpPopup, (visible) => {
  if (visible) {
    jumpInput.value = String(safePage.value)
  }
})

function goToPage(page) {
  const number = Number(page)
  if (!Number.isFinite(number)) {
    return
  }
  const next = Math.max(1, Math.min(totalPages.value, Math.floor(number)))
  if (next !== safePage.value) {
    emit('update:modelValue', next)
  }
}

function handleItemClick(item) {
  if (item.type === 'page') {
    goToPage(item.value)
    return
  }
  const jumpStep = isMobile.value ? 3 : 5
  const direction = item.value === 'left' ? -1 : 1
  goToPage(safePage.value + direction * jumpStep)
}

function openJumpPopup() {
  showJumpPopup.value = true
}

function confirmJump() {
  const target = Number(jumpInput.value)
  if (!Number.isFinite(target)) {
    showToast('请输入有效页码')
    return
  }
  if (target < 1 || target > totalPages.value) {
    showToast(`页码范围为 1-${totalPages.value}`)
    return
  }
  goToPage(target)
  showJumpPopup.value = false
}
</script>

<style scoped>
.app-pagination {
  margin: 16px auto 10px;
  padding: 12px;
  border-radius: 16px;
  border: 1px solid var(--border-soft);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.24), rgba(255, 255, 255, 0.05));
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
}

.summary-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.summary-main {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.summary-sub {
  margin-top: 2px;
  margin-bottom: 12px;
  font-size: 12px;
  color: var(--text-secondary);
}

.jump-trigger {
  appearance: none;
  border: 1px solid rgba(25, 137, 250, 0.3);
  background: rgba(25, 137, 250, 0.08);
  color: var(--brand-600);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
  transition: all var(--motion-fast) var(--ease-standard);
}

.jump-trigger:hover {
  background: rgba(25, 137, 250, 0.14);
}

.pager-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}

.pager-btn {
  appearance: none;
  min-width: 34px;
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  background: var(--surface-1);
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  cursor: pointer;
  transition: all var(--motion-fast) var(--ease-standard);
}

.pager-btn:hover {
  border-color: rgba(25, 137, 250, 0.5);
  transform: translateY(-1px);
}

.pager-btn.active {
  border-color: var(--brand-500);
  background: var(--brand-500);
  color: #fff;
  box-shadow: 0 6px 14px rgba(25, 137, 250, 0.26);
}

.pager-btn.ellipsis {
  min-width: 30px;
  padding: 0 6px;
  color: var(--text-tertiary);
}

.pager-btn.nav-btn {
  min-width: 34px;
  width: 34px;
  padding: 0;
}

.pager-btn.edge-btn {
  min-width: 34px;
  width: 34px;
  padding: 0;
  font-size: 14px;
  letter-spacing: -0.5px;
}

.pager-btn:disabled {
  opacity: 0.42;
  cursor: not-allowed;
  transform: none;
}

.jump-popup {
  border-top-left-radius: 16px;
  border-top-right-radius: 16px;
}

.jump-panel {
  padding: 16px;
}

.jump-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.jump-hint {
  margin-top: 4px;
  margin-bottom: 12px;
  color: var(--text-secondary);
  font-size: 12px;
}

.jump-actions {
  margin-top: 12px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

@media (max-width: 767px) {
  .app-pagination {
    margin: 12px 0 8px;
    padding: 10px;
    border-radius: 14px;
  }

  .summary-main {
    font-size: 12px;
  }

  .summary-sub {
    font-size: 11px;
  }

  .pager-row {
    gap: 6px;
  }

  .pager-btn {
    min-width: 32px;
    height: 32px;
    padding: 0 8px;
    border-radius: 9px;
    font-size: 12px;
  }

  .pager-btn.nav-btn {
    min-width: 32px;
    width: 32px;
  }

  .pager-btn.edge-btn {
    min-width: 32px;
    width: 32px;
    font-size: 13px;
  }
}
</style>
