<template>
  <nav v-if="totalItems > 0" class="app-pagination" aria-label="分页导航">
    <div class="pager-swap">
      <div class="pager-row" :class="{ 'is-hidden': showJumpInput }">
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

      <div class="jump-row" :class="{ 'is-visible': showJumpInput }">
        <input
          ref="jumpInputRef"
          v-model="jumpInput"
          type="number"
          class="jump-input"
          :placeholder="`1-${totalPages}`"
          @keyup.enter="confirmJump"
        />
        <button type="button" class="pager-btn jump-confirm" @click="confirmJump">跳转</button>
        <button type="button" class="pager-btn jump-cancel" @click="showJumpInput = false">取消</button>
      </div>
    </div>
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
  },
  hasMore: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue'])

const showJumpInput = ref(false)
const jumpInput = ref('')
const jumpInputRef = ref(null)
const { isMobile } = useDevice()

const safePageSize = computed(() => {
  const value = Number(props.pageSize)
  if (Number.isFinite(value) && value > 0) {
    return Math.floor(value)
  }
  return 20
})

const totalPages = computed(() => {
  const basePages = props.totalItems <= 0
    ? 1
    : Math.max(1, Math.ceil(props.totalItems / safePageSize.value))
  return basePages + (props.hasMore ? 1 : 0)
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
  const isProvisionalLastPage = props.hasMore
    && safePage.value === totalPages.value
    && start > props.totalItems
  const end = isProvisionalLastPage
    ? start + safePageSize.value - 1
    : Math.min(props.totalItems, start + safePageSize.value - 1)
  return { start, end }
})

const totalItemsLabel = computed(() => {
  if (props.totalItems <= 0) {
    return '0'
  }
  return props.hasMore ? `${props.totalItems}+` : String(props.totalItems)
})

const pageItems = computed(() => {
  const total = totalPages.value
  const current = safePage.value

  if (isMobile.value) {
    if (total <= 5) {
      return Array.from({ length: total }, (_, index) => ({
        key: `p-${index + 1}`,
        type: 'page',
        value: index + 1
      }))
    }

    if (current <= 2) {
      return [
        { key: 'p-1', type: 'page', value: 1 },
        { key: 'p-2', type: 'page', value: 2 },
        { key: 'p-3', type: 'page', value: 3 },
        { key: 'ellipsis-right', type: 'ellipsis', value: 'right' },
        { key: `p-${total}`, type: 'page', value: total }
      ]
    }

    if (current >= total - 1) {
      return [
        { key: 'p-1', type: 'page', value: 1 },
        { key: 'ellipsis-left', type: 'ellipsis', value: 'left' },
        { key: `p-${total - 2}`, type: 'page', value: total - 2 },
        { key: `p-${total - 1}`, type: 'page', value: total - 1 },
        { key: `p-${total}`, type: 'page', value: total }
      ]
    }

    return [
      { key: 'p-1', type: 'page', value: 1 },
      { key: 'ellipsis-left', type: 'ellipsis', value: 'left' },
      { key: `p-${current}`, type: 'page', value: current },
      { key: 'ellipsis-right', type: 'ellipsis', value: 'right' },
      { key: `p-${total}`, type: 'page', value: total }
    ]
  }

  if (total <= 7) {
    return Array.from({ length: total }, (_, index) => ({
      key: `p-${index + 1}`,
      type: 'page',
      value: index + 1
    }))
  }

  const items = []
  for (let page = 1; page <= 7; page += 1) {
    items.push({ key: `p-${page}`, type: 'page', value: page })
  }
  items.push({ key: 'ellipsis-right', type: 'ellipsis', value: 'right' })
  items.push({ key: `p-${total}`, type: 'page', value: total })
  return items
})

watch(showJumpInput, (visible) => {
  if (visible) {
    jumpInput.value = String(safePage.value)
    setTimeout(() => jumpInputRef.value?.focus(), 50)
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
  openJumpInput()
}

function openJumpInput() {
  showJumpInput.value = true
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
  showJumpInput.value = false
}
</script>

<style scoped>
.app-pagination {
  margin: 16px auto 10px;
  padding: 10px 12px;
  border-radius: 16px;
  border: 1px solid var(--border-soft);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.24), rgba(255, 255, 255, 0.05));
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
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

.pager-swap {
  position: relative;
  display: flex;
  justify-content: center;
  min-height: 34px;
  overflow: hidden;
}

.pager-row,
.jump-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex-wrap: wrap;
  transition: transform 220ms var(--ease-standard), opacity 220ms var(--ease-standard);
}

.jump-row {
  position: absolute;
  inset: 0;
  transform: translateX(120%);
  opacity: 0;
  pointer-events: none;
}

.jump-row.is-visible {
  transform: translateX(0);
  opacity: 1;
  pointer-events: auto;
}

.pager-row.is-hidden {
  transform: translateX(-120%);
  opacity: 0;
  pointer-events: none;
}

.jump-input {
  width: 72px;
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  background: var(--surface-1);
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
  text-align: center;
  outline: none;
  font-family: inherit;
  -moz-appearance: textfield;
}

.jump-input::-webkit-inner-spin-button,
.jump-input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.jump-input:focus {
  border-color: var(--brand-500);
}

.jump-confirm {
  min-width: 50px;
}

.jump-cancel {
  min-width: 50px;
  color: var(--text-secondary);
}

@media (max-width: 767px) {
  .app-pagination {
    margin: 12px 0 8px;
    padding: 10px;
    border-radius: 14px;
  }

  .pager-row {
    gap: 6px;
    flex-wrap: nowrap;
    min-width: 0;
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

@media (max-width: 380px) {
  .app-pagination {
    padding: 8px 7px;
  }

  .pager-row {
    gap: 4px;
  }

  .pager-btn {
    min-width: 28px;
    width: auto;
    height: 30px;
    padding: 0 6px;
    border-radius: 8px;
    font-size: 11px;
  }

  .pager-btn.nav-btn,
  .pager-btn.edge-btn {
    min-width: 28px;
    width: 28px;
  }
}
</style>
