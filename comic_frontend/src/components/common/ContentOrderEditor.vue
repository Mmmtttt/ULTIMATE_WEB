<template>
  <van-popup
    :show="show"
    :position="isDesktop ? 'center' : 'bottom'"
    round
    class="content-order-editor-popup"
    :style="popupStyle"
    @update:show="emit('update:show', $event)"
  >
    <div class="content-order-editor">
      <van-nav-bar title="自定义排序" left-text="关闭" @click-left="close">
        <template #right>
          <van-button type="primary" size="small" @click="saveOrder">保存</van-button>
        </template>
      </van-nav-bar>

      <div class="content-order-editor__intro">
        <p>这里管理当前内容库的完整顺序。</p>
        <p>初始顺序按导入时间生成；后续保存后会一直按这里的顺序显示。</p>
      </div>

      <div v-if="draftItems.length === 0" class="content-order-editor__empty">
        暂无可排序内容
      </div>

      <div v-else class="content-order-editor__list">
        <div
          v-for="(item, index) in draftItems"
          :key="item.id"
          class="content-order-editor__item"
        >
          <div class="content-order-editor__rank">{{ index + 1 }}</div>
          <div class="content-order-editor__cover">
            <img
              v-if="item.cover"
              :src="item.cover"
              :alt="item.title"
              loading="lazy"
            >
            <div v-else class="content-order-editor__cover-fallback">
              {{ item.shortTitle }}
            </div>
          </div>
          <div class="content-order-editor__meta">
            <div class="content-order-editor__title">{{ item.title }}</div>
            <div class="content-order-editor__subtitle">
              {{ item.platformLabel }}
            </div>
          </div>
          <div class="content-order-editor__controls">
            <button
              type="button"
              class="content-order-editor__icon-btn"
              :disabled="index === 0"
              aria-label="置顶"
              @click="moveToTop(index)"
            >
              <van-icon name="back-top" />
            </button>
            <button
              type="button"
              class="content-order-editor__icon-btn"
              :disabled="index === 0"
              aria-label="上移"
              @click="moveBy(index, -1)"
            >
              <van-icon name="arrow-up" />
            </button>
            <button
              type="button"
              class="content-order-editor__icon-btn"
              :disabled="index >= draftItems.length - 1"
              aria-label="下移"
              @click="moveBy(index, 1)"
            >
              <van-icon name="arrow-down" />
            </button>
            <button
              type="button"
              class="content-order-editor__icon-btn"
              :disabled="index >= draftItems.length - 1"
              aria-label="置底"
              @click="moveToBottom(index)"
            >
              <van-icon name="back-top" class="content-order-editor__bottom-icon" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </van-popup>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useDevice } from '@/composables/useDevice'

const props = defineProps({
  show: {
    type: Boolean,
    default: false,
  },
  items: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:show', 'save'])
const { isDesktop } = useDevice()

const draftItems = ref([])

const popupStyle = computed(() => (
  isDesktop.value
    ? { width: 'min(860px, 92vw)', height: 'min(88vh, 900px)' }
    : { height: '86vh' }
))

function normalizeItems(items = []) {
  return (Array.isArray(items) ? items : []).map((item, index) => {
    const title = String(item?.title || item?.name || item?.id || `内容 ${index + 1}`).trim()
    return {
      id: String(item?.id || `item-${index}`),
      title,
      cover: String(item?.cover || '').trim(),
      shortTitle: title.slice(0, 2) || '内容',
      platformLabel: String(item?.platformLabel || item?.platform || '').trim(),
    }
  })
}

function syncDraftItems() {
  draftItems.value = normalizeItems(props.items)
}

function close() {
  emit('update:show', false)
}

function moveBy(index, offset) {
  const nextIndex = index + offset
  if (index < 0 || nextIndex < 0 || nextIndex >= draftItems.value.length) {
    return
  }
  const nextItems = [...draftItems.value]
  const [target] = nextItems.splice(index, 1)
  nextItems.splice(nextIndex, 0, target)
  draftItems.value = nextItems
}

function moveToTop(index) {
  if (index <= 0) {
    return
  }
  const nextItems = [...draftItems.value]
  const [target] = nextItems.splice(index, 1)
  nextItems.unshift(target)
  draftItems.value = nextItems
}

function moveToBottom(index) {
  if (index < 0 || index >= draftItems.value.length - 1) {
    return
  }
  const nextItems = [...draftItems.value]
  const [target] = nextItems.splice(index, 1)
  nextItems.push(target)
  draftItems.value = nextItems
}

function saveOrder() {
  emit('save', draftItems.value.map((item) => item.id))
}

watch(
  () => props.items,
  () => {
    syncDraftItems()
  },
  { deep: true, immediate: true },
)

watch(
  () => props.show,
  (visible) => {
    if (visible) {
      syncDraftItems()
    }
  },
)
</script>

<style scoped>
.content-order-editor-popup {
  overflow: hidden;
}

.content-order-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--surface-base);
}

.content-order-editor__intro {
  padding: 12px 16px 4px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.content-order-editor__intro p {
  margin: 0;
}

.content-order-editor__empty {
  padding: 48px 20px;
  text-align: center;
  color: var(--text-tertiary);
}

.content-order-editor__list {
  flex: 1;
  overflow: auto;
  padding: 8px 12px 20px;
}

.content-order-editor__item {
  display: grid;
  grid-template-columns: 36px 54px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  background: var(--surface-elevated);
}

.content-order-editor__item + .content-order-editor__item {
  margin-top: 10px;
}

.content-order-editor__rank {
  color: var(--text-tertiary);
  font-size: 13px;
  text-align: center;
}

.content-order-editor__cover {
  width: 54px;
  height: 72px;
  border-radius: 6px;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.06);
}

.content-order-editor__cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.content-order-editor__cover-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  color: var(--text-secondary);
  font-size: 12px;
}

.content-order-editor__meta {
  min-width: 0;
}

.content-order-editor__title {
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.4;
  word-break: break-word;
}

.content-order-editor__subtitle {
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: 12px;
}

.content-order-editor__controls {
  display: grid;
  grid-template-columns: repeat(2, 34px);
  gap: 8px;
}

.content-order-editor__icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}

.content-order-editor__icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.content-order-editor__bottom-icon {
  transform: rotate(180deg);
}

@media (max-width: 640px) {
  .content-order-editor__item {
    grid-template-columns: 30px 48px minmax(0, 1fr);
    gap: 10px;
  }

  .content-order-editor__cover {
    width: 48px;
    height: 64px;
  }

  .content-order-editor__controls {
    grid-column: 2 / -1;
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .content-order-editor__icon-btn {
    width: 100%;
  }
}
</style>
