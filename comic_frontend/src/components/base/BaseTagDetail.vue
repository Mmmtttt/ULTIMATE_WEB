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
            :items="homeItems" 
            :class="{ 'video-mode': isVideo }"
            @click="goToHomeItem" 
          />
        </van-tab>

        <van-tab :title="`推荐${contentLabel}`">
          <div v-if="recommendationItems.length === 0" class="empty-section">
            <van-empty :description="`推荐页暂无此标签的${contentLabel}`" />
          </div>
          <MediaGrid 
            v-else 
            :items="recommendationItems" 
            :class="{ 'video-mode': isVideo }"
            @click="goToRecommendationItem" 
          />
        </van-tab>

        <van-tab :title="`全部 (${totalCount})`">
          <div v-if="allItems.length === 0" class="empty-section">
            <van-empty :description="`暂无此标签的${contentLabel}`" />
          </div>
          <MediaGrid 
            v-else 
            :items="allItems" 
            :class="{ 'video-mode': isVideo }"
            @click="goToItem" 
          />
        </van-tab>
      </van-tabs>
    </div>

    <van-popup v-model:show="showEditPopup" round position="bottom" :style="{ height: '30%' }">
      <div class="edit-popup">
        <van-nav-bar title="编辑标签" left-text="取消" @click-left="showEditPopup = false">
          <template #right>
            <van-button type="primary" size="small" @click="saveEdit">保存</van-button>
          </template>
        </van-nav-bar>
        <van-field
          v-model="editTagName"
          label="标签名称"
          placeholder="请输入标签名称"
          :rules="[{ required: true, message: '请输入标签名称' }]"
        />
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showSuccessToast, showFailToast } from 'vant'
import MediaGrid from '@/components/common/MediaGrid.vue'

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
  fetchTagDetail()
})
</script>

<style scoped>
.base-tag-detail {
  min-height: 100vh;
  background: #f5f5f5;
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
  background: #fff;
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
  color: #666;
  margin-top: 4px;
}

.empty-section {
  padding: 40px 0;
}

.edit-popup {
  padding-bottom: 20px;
}
</style>
