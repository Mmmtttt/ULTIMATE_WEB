<template>
  <div class="base-tag-detail">
    <van-nav-bar 
      :title="tagInfo.name || '标签详情'" 
      left-text="返回" 
      left-arrow 
      @click-left="$router.back()"
    >
      <template #right>
        <van-icon name="edit" @click="openEditPopup" />
      </template>
    </van-nav-bar>

    <van-loading v-if="isLoading" type="spinner" color="#1989fa" class="loading-center" />

    <div v-else class="content">
      <div class="tag-stats">
        <div class="stat-item">
          <span class="stat-value">{{ homeCount }}</span>
          <span class="stat-label">主页{{ contentLabel }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ recommendationCount }}</span>
          <span class="stat-label">推荐{{ contentLabel }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ totalCount }}</span>
          <span class="stat-label">总计</span>
        </div>
      </div>

      <van-tabs v-model:active="activeTab" sticky>
        <van-tab :title="`主页${contentLabel}`">
          <div v-if="homeItems.length === 0" class="empty-section">
            <van-empty :description="`主页暂无此标签的${contentLabel}`" />
          </div>
          <MediaGrid 
            v-else 
            :items="pagedHomeItems" 
            :content-type="props.contentType"
            :class="{ 'video-mode': isVideo }"
            @click="goToHomeItem" 
          />
          <AppPagination
            v-if="homeItems.length > 0"
            v-model="homeCurrentPage"
            class="tag-pagination"
            :total-items="homeTotalItems"
            :page-size="homePageSize"
          />
        </van-tab>

        <van-tab :title="`推荐${contentLabel}`">
          <div v-if="recommendationItems.length === 0" class="empty-section">
            <van-empty :description="`推荐页暂无此标签的${contentLabel}`" />
          </div>
          <MediaGrid 
            v-else 
            :items="pagedRecommendationItems" 
            :content-type="props.contentType"
            :class="{ 'video-mode': isVideo }"
            @click="goToRecommendationItem" 
          />
          <AppPagination
            v-if="recommendationItems.length > 0"
            v-model="recommendationCurrentPage"
            class="tag-pagination"
            :total-items="recommendationTotalItems"
            :page-size="recommendationPageSize"
          />
        </van-tab>

        <van-tab :title="`全部 (${totalCount})`">
          <div v-if="allItems.length === 0" class="empty-section">
            <van-empty :description="`暂无此标签的${contentLabel}`" />
          </div>
          <MediaGrid 
            v-else 
            :items="pagedAllItems" 
            :content-type="props.contentType"
            :class="{ 'video-mode': isVideo }"
            @click="goToItem" 
          />
          <AppPagination
            v-if="allItems.length > 0"
            v-model="allCurrentPage"
            class="tag-pagination"
            :total-items="allTotalItems"
            :page-size="allPageSize"
          />
        </van-tab>
      </van-tabs>
    </div>

    <van-popup
      v-model:show="showEditPopup"
      round
      position="center"
      :style="{ width: 'min(420px, calc(100vw - 32px))' }"
    >
      <div class="edit-popup">
        <div class="edit-popup__header">
          <div>
            <div class="edit-popup__title">编辑标签</div>
            <div class="edit-popup__desc">修改名称后会同步影响所有已绑定内容的显示。</div>
          </div>
          <button type="button" class="edit-popup__close" @click="showEditPopup = false">
            <van-icon name="cross" />
          </button>
        </div>
        <van-field
          v-model="editTagName"
          label="标签名称"
          placeholder="请输入标签名称"
          :rules="[{ required: true, message: '请输入标签名称' }]"
        />
        <div class="edit-popup__actions">
          <van-button round plain @click="showEditPopup = false">取消</van-button>
          <van-button round type="primary" @click="saveEdit">保存</van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showSuccessToast, showFailToast } from 'vant'
import MediaGrid from '@/components/common/MediaGrid.vue'
import AppPagination from '@/components/common/AppPagination.vue'
import { useClientPagination } from '@/composables/useClientPagination'
import { clearBrowseState, loadBrowseState, saveBrowseState } from '@/utils'

const props = defineProps({
  contentType: {
    type: String,
    required: true,
    validator: (v) => ['comic', 'video'].includes(v)
  },
  tagStore: {
    type: Object,
    required: true
  },
  tagApi: {
    type: Object,
    required: true
  },
  homeDetailRoute: {
    type: String,
    default: 'ComicDetail'
  },
  recommendationDetailRoute: {
    type: String,
    default: 'RecommendationDetail'
  }
})

const route = useRoute()
const router = useRouter()

const isLoading = ref(true)
const activeTab = ref(0)
const tagInfo = ref({})
const homeItems = ref([])
const recommendationItems = ref([])

const showEditPopup = ref(false)
const editTagName = ref('')

const isVideo = computed(() => props.contentType === 'video')

const contentLabel = computed(() => isVideo.value ? '视频' : '漫画')

const homeCount = computed(() => homeItems.value.length)

const recommendationCount = computed(() => recommendationItems.value.length)

const totalCount = computed(() => homeCount.value + recommendationCount.value)

const allItems = computed(() => {
  const homeWithSource = homeItems.value.map(item => ({ ...item, source: 'home' }))
  const recWithSource = recommendationItems.value.map(item => ({ ...item, source: 'recommendation' }))
  return [...homeWithSource, ...recWithSource]
})

const {
  pageSize: homePageSize,
  currentPage: homeCurrentPage,
  totalItems: homeTotalItems,
  pagedItems: pagedHomeItems,
} = useClientPagination(homeItems, computed(() => `tag_detail_home_${props.contentType}_${route.params.id}`))

const {
  pageSize: recommendationPageSize,
  currentPage: recommendationCurrentPage,
  totalItems: recommendationTotalItems,
  pagedItems: pagedRecommendationItems,
} = useClientPagination(recommendationItems, computed(() => `tag_detail_recommendation_${props.contentType}_${route.params.id}`))

const {
  pageSize: allPageSize,
  currentPage: allCurrentPage,
  totalItems: allTotalItems,
  pagedItems: pagedAllItems,
} = useClientPagination(allItems, computed(() => `tag_detail_all_${props.contentType}_${route.params.id}`))

function getBrowseStateKey() {
  return `tag_detail_state_${props.contentType}_${route.params.id}`
}

function persistBrowseState() {
  if (activeTab.value <= 0) {
    clearBrowseState(getBrowseStateKey())
    return
  }
  saveBrowseState(getBrowseStateKey(), { activeTab: activeTab.value })
}

function restoreBrowseState() {
  const parsed = loadBrowseState(getBrowseStateKey(), null)
  if (!parsed) {
    return
  }
  if (Number(parsed.activeTab) >= 0) {
    activeTab.value = Math.max(0, Math.floor(Number(parsed.activeTab)))
  }
}

async function fetchTagDetail() {
  const tagId = route.params.id
  if (!tagId) {
    showFailToast('标签ID不存在')
    router.back()
    return
  }

  isLoading.value = true
  try {
    const response = isVideo.value
      ? await props.tagApi.getVideos(tagId)
      : await props.tagApi.getComics(tagId)
    
    if (response.code === 200) {
      tagInfo.value = response.data.tag || {}
      if (isVideo.value) {
        homeItems.value = response.data.home_videos || []
        recommendationItems.value = response.data.recommendation_videos || []
      } else {
        homeItems.value = response.data.home_comics || []
        recommendationItems.value = response.data.recommendation_comics || []
      }
    } else {
      showFailToast(response.msg || '获取标签详情失败')
    }
  } catch (error) {
    console.error('获取标签详情失败:', error)
    showFailToast('获取标签详情失败')
  } finally {
    isLoading.value = false
  }
}

function goToHomeItem(item) {
  router.push({ name: props.homeDetailRoute, params: { id: item.id } })
}

function goToRecommendationItem(item) {
  router.push({ name: props.recommendationDetailRoute, params: { id: item.id } })
}

function goToItem(item) {
  const routeName = item.source === 'home' 
    ? props.homeDetailRoute 
    : props.recommendationDetailRoute
  router.push({ name: routeName, params: { id: item.id } })
}

function openEditPopup() {
  editTagName.value = tagInfo.value.name || ''
  showEditPopup.value = true
}

async function saveEdit() {
  if (!editTagName.value.trim()) {
    showFailToast('请输入标签名称')
    return
  }

  try {
    const response = isVideo.value
      ? await props.tagStore.editVideoTag(tagInfo.value.id, editTagName.value.trim())
      : await props.tagStore.editTag(tagInfo.value.id, editTagName.value.trim())
    
    if (response.success) {
      tagInfo.value.name = editTagName.value.trim()
      showEditPopup.value = false
      showSuccessToast('修改成功')
    } else {
      showFailToast(response.message || '修改失败')
    }
  } catch (error) {
    console.error('修改标签失败:', error)
    showFailToast('修改失败')
  }
}

onMounted(() => {
  restoreBrowseState()
  fetchTagDetail()
})

watch(activeTab, () => {
  persistBrowseState()
})
</script>

<style scoped>
.base-tag-detail {
  min-height: 100vh;
  background: var(--surface-0);
}

.loading-center {
  display: flex;
  justify-content: center;
  padding: 100px 0;
}

.content {
  padding-bottom: 20px;
}

.tag-stats {
  display: flex;
  justify-content: space-around;
  padding: 20px;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  margin-bottom: 10px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #1989fa;
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.empty-section {
  padding: 40px 0;
}

.edit-popup {
  padding: 16px;
  background: var(--surface-2);
}

.edit-popup__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 14px;
}

.edit-popup__title {
  font-size: 18px;
  font-weight: 800;
  color: var(--text-strong);
}

.edit-popup__desc {
  margin-top: 5px;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.5;
}

.edit-popup__close {
  display: inline-grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 999px;
  background: var(--surface-1);
  color: var(--text-secondary);
  cursor: pointer;
}

.edit-popup :deep(.van-cell) {
  border-radius: 14px;
  background: var(--surface-1);
}

.edit-popup__actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.tag-pagination {
  margin-top: 6px;
}
</style>
