<template>
  <div class="home">
    <van-nav-bar title="漫画库" />
    
    <!-- 搜索栏 -->
    <div class="search-bar">
      <van-search
        v-model="searchQuery"
        placeholder="搜索漫画"
        @search="handleSearch"
        shape="round"
      />
    </div>
    
    <!-- 分类标签 -->
    <div class="category-tabs">
      <van-tabs v-model:active="activeCategory" type="card" background="#f5f5f5">
        <van-tab v-for="category in categories" :key="category.value" :title="category.text" :name="category.value" />
      </van-tabs>
    </div>
    
    <!-- 漫画列表 -->
    <van-loading v-if="comicStore.isLoading" type="spinner" color="#1989fa" />
    
    <div v-else-if="comicStore.comicList.length === 0" class="empty">
      <van-empty description="暂无漫画" />
      <van-button type="primary" @click="goToMine">去导入漫画</van-button>
    </div>
    
    <div v-else class="comic-grid">
      <div 
        v-for="comic in comicStore.comicList" 
        :key="comic.id" 
        class="comic-card" 
        @click="goToDetail(comic.id)"
        @mouseenter="showTooltip(comic, $event)"
        @mouseleave="hideTooltip"
      >
        <div class="comic-cover-container">
          <van-image 
            :src="getCoverUrl(comic.cover_path)" 
            fit="cover" 
            class="comic-cover"
            lazy-load
          />
          <div class="comic-badge" v-if="comic.current_page > 1">
            {{ Math.round((comic.current_page / comic.total_page) * 100) }}%
          </div>
        </div>
        <div class="comic-info">
          <h3 class="comic-title">{{ comic.title }}</h3>
          <div class="comic-meta">
            <span class="page-info">{{ comic.current_page }}/{{ comic.total_page }}</span>
            <span class="author">{{ comic.author || '未知' }}</span>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 标签提示框 -->
    <div v-if="tooltipVisible" class="tags-tooltip" :style="tooltipStyle">
      <div class="tooltip-content">
        <h4>{{ tooltipComic.title }}</h4>
        <div class="tooltip-tags">
          <van-tag 
            v-for="tag in tooltipTags" 
            :key="tag" 
            size="small" 
            type="primary"
            class="tooltip-tag"
          >
            {{ tag }}
          </van-tag>
          <span v-if="tooltipTags.length === 0" class="no-tags">暂无标签</span>
        </div>
      </div>
    </div>
    
    <!-- 底部导航 -->
    <van-tabbar v-model="active" route>
      <van-tabbar-item icon="home-o" to="/">主页</van-tabbar-item>
      <van-tabbar-item icon="user-o" to="/mine">我的</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useComicStore } from '../store/modules/comic'
import apiConfig from '../config/api'

const router = useRouter()
const comicStore = useComicStore()
const active = ref(0)
const searchQuery = ref('')
const activeCategory = ref(0)
const categories = [
  { text: '全部', value: 0 },
  { text: '热门', value: 1 },
  { text: '最新', value: 2 },
  { text: '已读', value: 3 }
]

const getCoverUrl = (coverPath) => {
  return apiConfig.getCoverUrl(coverPath)
}

const goToDetail = (id) => {
  console.log('点击漫画，跳转到详情页:', id)
  router.push(`/comic/${id}`)
}

const goToMine = () => {
  console.log('点击去导入漫画')
  router.push('/mine')
}

const handleSearch = (value) => {
  console.log('搜索:', value)
}

const tooltipVisible = ref(false)
const tooltipComic = ref({})
const tooltipTags = ref([])
const tooltipStyle = ref({})
const allTags = ref([])

const fetchAllTags = async () => {
  try {
    const response = await fetch(`${apiConfig.getFullUrl('/api/v1/comic/tags')}`)
    const result = await response.json()
    if (result.code === 200) {
      allTags.value = result.data
    }
  } catch (error) {
    console.error('获取标签失败:', error)
  }
}

const getTagName = (tagId) => {
  const tag = allTags.value.find(t => t.id === tagId)
  return tag ? tag.name : tagId
}

const showTooltip = (comic, event) => {
  tooltipComic.value = comic
  tooltipTags.value = (comic.tag_ids || []).map(getTagName)
  
  const rect = event.target.getBoundingClientRect()
  tooltipStyle.value = {
    left: `${rect.left + rect.width / 2}px`,
    top: `${rect.top - 10}px`,
    transform: 'translate(-50%, -100%)'
  }
  
  tooltipVisible.value = true
}

const hideTooltip = () => {
  tooltipVisible.value = false
}

onMounted(async () => {
  console.log('Home页面加载，开始获取漫画列表')
  await comicStore.fetchComics()
  await fetchAllTags()
  console.log('漫画列表获取完成:', comicStore.comicList)
})
</script>

<style scoped>
.home {
  padding-bottom: 50px;
  min-height: 100vh;
  background: #f5f5f5;
}

.search-bar {
  padding: 10px 16px;
  background: #fff;
}

.category-tabs {
  background: #fff;
  margin-bottom: 10px;
}

.comic-grid {
  padding: 10px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
}

.comic-card {
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
  cursor: pointer;
}

.comic-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.comic-cover-container {
  position: relative;
  width: 100%;
  padding-top: 140%;
  overflow: hidden;
}

.comic-cover {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: #f0f0f0;
}

.comic-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
}

.comic-info {
  padding: 8px;
}

.comic-title {
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

.comic-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 10px;
  color: #999;
}

.page-info {
  flex: 1;
}

.author {
  flex: 1;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty {
  padding: 40px 0;
  text-align: center;
}

.empty .van-button {
  margin-top: 20px;
}

.tags-tooltip {
  position: fixed;
  z-index: 9999;
  pointer-events: none;
}

.tooltip-content {
  background: rgba(0, 0, 0, 0.9);
  color: #fff;
  padding: 12px 16px;
  border-radius: 8px;
  max-width: 250px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.tooltip-content h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tooltip-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tooltip-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 12px;
}

.no-tags {
  font-size: 11px;
  color: #999;
  font-style: italic;
}

.tags-tooltip::after {
  content: '';
  position: absolute;
  bottom: -8px;
  left: 50%;
  transform: translateX(-50%);
  border-left: 8px solid transparent;
  border-right: 8px solid transparent;
  border-top: 8px solid rgba(0, 0, 0, 0.9);
}
</style>
