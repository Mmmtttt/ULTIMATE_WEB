<template>
  <div class="video-tag-detail">
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
          <span class="stat-value">{{ homeVideos.length }}</span>
          <span class="stat-label">主页视频</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ recommendationVideos.length }}</span>
          <span class="stat-label">推荐视频</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ totalCount }}</span>
          <span class="stat-label">总计</span>
        </div>
      </div>

      <van-tabs v-model:active="activeTab" sticky>
        <van-tab title="主页视频">
          <div v-if="homeVideos.length === 0" class="empty-section">
            <van-empty description="主页暂无此标签的视频" />
          </div>
          <div v-else class="video-grid">
            <div 
              v-for="item in homeVideos" 
              :key="item.id" 
              class="video-card"
              @click="goToHomeVideo(item)"
            >
              <div class="video-cover">
                <van-image 
                  :src="getCoverUrl(item.cover_path)" 
                  fit="cover" 
                  class="cover-image"
                  lazy-load
                />
                <div v-if="item.code" class="video-code">{{ item.code }}</div>
                <div v-if="item.score" class="video-score">{{ item.score }}</div>
              </div>
              <div class="video-info">
                <div class="video-title">{{ item.title }}</div>
                <div v-if="item.tags && item.tags.length > 0" class="video-tags">
                  <van-tag 
                    v-for="(tag, index) in item.tags.slice(0, 2)" 
                    :key="tag.id || index" 
                    size="mini" 
                    type="primary" 
                    plain
                    class="video-tag"
                  >
                    {{ tag.name }}
                  </van-tag>
                </div>
                <div v-if="item.date" class="video-date">{{ item.date }}</div>
              </div>
            </div>
          </div>
        </van-tab>

        <van-tab title="推荐视频">
          <div v-if="recommendationVideos.length === 0" class="empty-section">
            <van-empty description="推荐页暂无此标签的视频" />
          </div>
          <div v-else class="video-grid">
            <div 
              v-for="item in recommendationVideos" 
              :key="item.id" 
              class="video-card"
              @click="goToRecommendationVideo(item)"
            >
              <div class="video-cover">
                <van-image 
                  :src="getCoverUrl(item.cover_path)" 
                  fit="cover" 
                  class="cover-image"
                  lazy-load
                />
                <div v-if="item.code" class="video-code">{{ item.code }}</div>
                <div v-if="item.score" class="video-score">{{ item.score }}</div>
              </div>
              <div class="video-info">
                <div class="video-title">{{ item.title }}</div>
                <div v-if="item.tags && item.tags.length > 0" class="video-tags">
                  <van-tag 
                    v-for="(tag, index) in item.tags.slice(0, 2)" 
                    :key="tag.id || index" 
                    size="mini" 
                    type="primary" 
                    plain
                    class="video-tag"
                  >
                    {{ tag.name }}
                  </van-tag>
                </div>
                <div v-if="item.date" class="video-date">{{ item.date }}</div>
              </div>
            </div>
          </div>
        </van-tab>

        <van-tab :title="`全部 (${totalCount})`">
          <div v-if="allVideos.length === 0" class="empty-section">
            <van-empty description="暂无此标签的视频" />
          </div>
          <div v-else class="video-grid">
            <div 
              v-for="item in allVideos" 
              :key="item.id" 
              class="video-card"
              @click="goToVideo(item)"
            >
              <div class="video-cover">
                <van-image 
                  :src="getCoverUrl(item.cover_path)" 
                  fit="cover" 
                  class="cover-image"
                  lazy-load
                />
                <div v-if="item.code" class="video-code">{{ item.code }}</div>
                <div v-if="item.score" class="video-score">{{ item.score }}</div>
              </div>
              <div class="video-info">
                <div class="video-title">{{ item.title }}</div>
                <div v-if="item.tags && item.tags.length > 0" class="video-tags">
                  <van-tag 
                    v-for="(tag, index) in item.tags.slice(0, 2)" 
                    :key="tag.id || index" 
                    size="mini" 
                    type="primary" 
                    plain
                    class="video-tag"
                  >
                    {{ tag.name }}
                  </van-tag>
                </div>
                <div v-if="item.date" class="video-date">{{ item.date }}</div>
              </div>
            </div>
          </div>
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
import { tagApi, imageApi } from '@/api'
import { useTagStore } from '@/stores'

const route = useRoute()
const router = useRouter()
const tagStore = useTagStore()

const isLoading = ref(true)
const activeTab = ref(0)
const tagInfo = ref({})
const homeVideos = ref([])
const recommendationVideos = ref([])

const showEditPopup = ref(false)
const editTagName = ref('')

const totalCount = computed(() => homeVideos.value.length + recommendationVideos.value.length)

const allVideos = computed(() => {
  const homeWithSource = homeVideos.value.map(v => ({ ...v, source: 'home' }))
  const recWithSource = recommendationVideos.value.map(v => ({ ...v, source: 'recommendation' }))
  return [...homeWithSource, ...recWithSource]
})

function getCoverUrl(coverPath) {
  if (!coverPath) return ''
  return imageApi.getCoverUrl(coverPath)
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
    const response = await tagApi.getVideos(tagId)
    if (response.code === 200) {
      tagInfo.value = response.data.tag || {}
      homeVideos.value = response.data.home_videos || []
      recommendationVideos.value = response.data.recommendation_videos || []
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

function goToHomeVideo(video) {
  router.push(`/video/${video.id}`)
}

function goToRecommendationVideo(video) {
  router.push(`/video-recommendation/${video.id}`)
}

function goToVideo(video) {
  if (video.source === 'home') {
    router.push(`/video/${video.id}`)
  } else {
    router.push(`/video-recommendation/${video.id}`)
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
    const response = await tagStore.editVideoTag(tagInfo.value.id, editTagName.value.trim())
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
.video-tag-detail {
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

.video-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 10px;
  padding: 10px;
}

@media (min-width: 768px) {
  .video-grid {
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 16px;
    padding: 16px;
  }
}

@media (min-width: 1200px) {
  .video-grid {
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 20px;
  }
}

.video-card {
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: all 0.3s ease;
}

.video-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.video-cover {
  position: relative;
  width: 100%;
  padding-top: 140%;
  overflow: hidden;
}

.cover-image {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: #f0f0f0;
}

.video-code {
  position: absolute;
  top: 8px;
  left: 8px;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
}

.video-score {
  position: absolute;
  bottom: 8px;
  left: 8px;
  background: rgba(255, 153, 0, 0.9);
  color: #fff;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
  font-weight: bold;
}

.video-info {
  padding: 8px;
}

.video-title {
  font-size: 12px;
  font-weight: 500;
  margin: 0 0 4px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-height: 1.3;
}

.video-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 4px;
}

.video-tag {
  font-size: 10px;
}

.video-date {
  font-size: 10px;
  color: #999;
}

.edit-popup {
  padding-bottom: 20px;
}

@media (max-width: 767px) {
  .video-card:hover {
    transform: none;
  }
  
  .video-card:active {
    transform: scale(0.98);
  }
}
</style>
