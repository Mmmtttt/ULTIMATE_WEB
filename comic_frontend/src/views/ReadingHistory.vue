<template>
  <div class="history-page desktop-page-shell">
    <section class="history-hero">
      <div>
        <p class="eyebrow">{{ isVideoMode ? 'Video History' : 'Comic History' }}</p>
        <h1>阅读记录</h1>
        <p class="subtitle">最近访问的{{ modeLabel }}会自动保留 30 条，本地库与预览库分开标记。</p>
      </div>
      <ModeSwitch class="history-mode-switch" />
    </section>

    <section class="history-panel">
      <div class="panel-header">
        <div>
          <h2>{{ modeLabel }}记录</h2>
          <span>{{ currentItems.length }} / 30</span>
        </div>
        <van-button size="small" round plain icon="replay" :loading="historyStore.loading" @click="reload">
          刷新
        </van-button>
      </div>

      <div v-if="historyStore.loading && currentItems.length === 0" class="loading-state">
        <van-loading size="24px">加载阅读记录...</van-loading>
      </div>

      <van-empty
        v-else-if="currentItems.length === 0"
        class="history-empty"
        image="search"
        :description="`还没有${modeLabel}访问记录`"
      />

      <div v-else class="history-grid" :class="{ 'video-mode': isVideoMode }">
        <button
          v-for="item in currentItems"
          :key="`${item.source}-${item.id}`"
          type="button"
          class="history-card"
          @click="openItem(item)"
        >
          <div class="cover-wrap">
            <img :src="getCoverUrl(item)" :alt="item.title || item.id" loading="lazy" />
            <span class="source-badge" :class="item.source">{{ item.source === 'preview' ? '预览' : '本地' }}</span>
          </div>
          <div class="card-body">
            <h3>{{ item.title || item.id }}</h3>
            <p v-if="isVideoMode" class="meta-line">{{ item.code || primaryActors(item) || '视频' }}</p>
            <p v-else class="meta-line">{{ item.author || '未知作者' }}</p>
            <div class="card-footer">
              <span v-if="item.score" class="score">{{ item.score }} 分</span>
              <span>{{ formatVisitedAt(item.visited_at) }}</span>
            </div>
          </div>
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import ModeSwitch from '@/components/common/ModeSwitch.vue'
import { useHistoryStore, useModeStore } from '@/stores'
import { buildCoverUrl } from '@/api/image'

const router = useRouter()
const modeStore = useModeStore()
const historyStore = useHistoryStore()

const isVideoMode = computed(() => modeStore.isVideoMode)
const contentType = computed(() => (isVideoMode.value ? 'video' : 'comic'))
const modeLabel = computed(() => (isVideoMode.value ? '视频' : '漫画'))
const currentItems = computed(() => (isVideoMode.value ? historyStore.videoItems : historyStore.comicItems))

function primaryActors(item) {
  const actors = Array.isArray(item?.actors) ? item.actors : []
  return actors.slice(0, 2).join(' / ')
}

function getCoverUrl(item) {
  return buildCoverUrl(item)
}

function formatVisitedAt(value) {
  const raw = String(value || '').trim()
  if (!raw) return '刚刚访问'
  const normalized = raw.replace('T', ' ')
  return normalized.length > 16 ? normalized.slice(0, 16) : normalized
}

function openItem(item) {
  if (!item?.id) return
  if (item.content_type === 'video') {
    router.push({ name: item.source === 'preview' ? 'VideoRecommendationDetail' : 'VideoDetail', params: { id: item.id } })
    return
  }
  router.push({ name: item.source === 'preview' ? 'RecommendationDetail' : 'ComicDetail', params: { id: item.id } })
}

async function reload() {
  await historyStore.fetchHistory(contentType.value)
}

onMounted(reload)

watch(contentType, reload)
</script>

<style scoped>
.history-page {
  padding: 14px 16px 24px;
}

.history-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: clamp(16px, 3vw, 26px);
  border: 1px solid var(--border-soft);
  border-radius: 24px;
  background:
    radial-gradient(circle at 12% 18%, rgba(80, 134, 255, 0.18), transparent 32%),
    linear-gradient(135deg, var(--surface-2), var(--surface-1));
  box-shadow: var(--shadow-sm);
}

.eyebrow {
  margin: 0 0 6px;
  color: var(--brand-600);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.history-hero h1,
.panel-header h2,
.history-card h3 {
  margin: 0;
}

.history-hero h1 {
  color: var(--text-primary);
  font-size: clamp(24px, 4vw, 34px);
  line-height: 1.15;
}

.subtitle {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.6;
}

.history-mode-switch {
  flex: 0 0 auto;
}

.history-panel {
  margin-top: 16px;
  padding: clamp(12px, 2vw, 18px);
  border: 1px solid var(--border-soft);
  border-radius: 22px;
  background: var(--surface-2);
  box-shadow: var(--shadow-xs);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.panel-header h2 {
  color: var(--text-primary);
  font-size: 18px;
}

.panel-header span {
  display: inline-block;
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: 12px;
}

.loading-state,
.history-empty {
  padding: 46px 0;
}

.history-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 14px;
}

.history-grid.video-mode {
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
}

.history-card {
  overflow: hidden;
  padding: 0;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  background: var(--surface-1);
  color: inherit;
  text-align: left;
  box-shadow: var(--shadow-xs);
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.history-card:hover {
  border-color: rgba(80, 134, 255, 0.45);
  box-shadow: var(--shadow-sm);
  transform: translateY(-2px);
}

.cover-wrap {
  position: relative;
  aspect-ratio: 3 / 4;
  background: var(--surface-3, rgba(148, 163, 184, 0.12));
}

.video-mode .cover-wrap {
  aspect-ratio: 16 / 10;
}

.cover-wrap img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.source-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.66);
  color: #fff;
  font-size: 11px;
  backdrop-filter: blur(8px);
}

.source-badge.preview {
  background: rgba(37, 99, 235, 0.78);
}

.card-body {
  padding: 10px 11px 12px;
}

.history-card h3 {
  min-height: 38px;
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.meta-line {
  margin: 7px 0 0;
  min-height: 18px;
  color: var(--text-secondary);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 9px;
  color: var(--text-tertiary);
  font-size: 11px;
}

.score {
  color: var(--brand-600);
  font-weight: 700;
}

@media (max-width: 640px) {
  .history-page {
    padding: 10px 10px 18px;
  }

  .history-hero {
    align-items: flex-start;
    flex-direction: column;
    border-radius: 20px;
  }

  .history-grid,
  .history-grid.video-mode {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }
}
</style>
