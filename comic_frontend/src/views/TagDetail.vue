<template>
  <div class="tag-detail">
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
          <span class="stat-value">{{ homeComics.length }}</span>
          <span class="stat-label">主页漫画</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ recommendationComics.length }}</span>
          <span class="stat-label">推荐漫画</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ totalCount }}</span>
          <span class="stat-label">总计</span>
        </div>
      </div>

      <van-tabs v-model:active="activeTab" sticky>
        <van-tab title="主页漫画">
          <div v-if="homeComics.length === 0" class="empty-section">
            <van-empty description="主页暂无此标签的漫画" />
          </div>
          <ComicGrid v-else :comics="homeComics" @card-click="goToHomeComic" />
        </van-tab>

        <van-tab title="推荐漫画">
          <div v-if="recommendationComics.length === 0" class="empty-section">
            <van-empty description="推荐页暂无此标签的漫画" />
          </div>
          <ComicGrid v-else :comics="recommendationComics" @card-click="goToRecommendationComic" />
        </van-tab>

        <van-tab :title="`全部 (${totalCount})`">
          <div v-if="allComics.length === 0" class="empty-section">
            <van-empty description="暂无此标签的漫画" />
          </div>
          <ComicGrid v-else :comics="allComics" @card-click="goToComic" />
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
import { tagApi } from '@/api'
import { useTagStore } from '@/stores'
import ComicGrid from '@/components/comic/ComicGrid.vue'

const route = useRoute()
const router = useRouter()
const tagStore = useTagStore()

const isLoading = ref(true)
const activeTab = ref(0)
const tagInfo = ref({})
const homeComics = ref([])
const recommendationComics = ref([])

const showEditPopup = ref(false)
const editTagName = ref('')

const totalCount = computed(() => homeComics.value.length + recommendationComics.value.length)

const allComics = computed(() => {
  const homeWithSource = homeComics.value.map(c => ({ ...c, source: 'home' }))
  const recWithSource = recommendationComics.value.map(c => ({ ...c, source: 'recommendation' }))
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
    const response = await tagApi.getComics(tagId)
    if (response.code === 200) {
      tagInfo.value = response.data.tag || {}
      homeComics.value = response.data.home_comics || []
      recommendationComics.value = response.data.recommendation_comics || []
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

function goToHomeComic(comic) {
  router.push(`/comic/${comic.id}`)
}

function goToRecommendationComic(comic) {
  router.push(`/recommendation/${comic.id}`)
}

function goToComic(comic) {
  if (comic.source === 'home') {
    router.push(`/comic/${comic.id}`)
  } else {
    router.push(`/recommendation/${comic.id}`)
  }
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
    const response = await tagStore.editTag(tagInfo.value.id, editTagName.value.trim())
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
.tag-detail {
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
