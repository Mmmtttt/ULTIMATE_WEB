<template>
  <div class="actor-page" :class="{ 'actor-page-desktop': isDesktop, 'actor-page-mobile': isMobile }">
    <van-nav-bar title="演员" left-text="返回" left-arrow @click-left="$router.back()">
      <template #right>
        <van-icon name="plus" @click="showAddPopup = true" />
      </template>
    </van-nav-bar>

    <van-loading v-if="loading" type="spinner" color="#1989fa" class="loading-center" />

    <div v-else-if="actors.length === 0" class="empty">
      <van-empty description="暂无订阅演员" />
    </div>

    <div v-else class="actor-list">
      <van-swipe-cell v-for="actor in actors" :key="actor.id">
        <van-cell is-link @click="showActorDetail(actor)">
          <template #title>
            <div class="actor-cell">
              <div class="actor-name">
                {{ actor.name }}
                <span v-if="actor.new_work_count > 0" class="new-badge">
                  {{ actor.new_work_count }} 个新作品
                </span>
              </div>
              <div class="actor-status">
                <span v-if="actor.last_work_title" class="last-work">
                  最新: {{ actor.last_work_title }}
                </span>
                <span v-else class="last-work">暂无作品记录</span>
              </div>
            </div>
          </template>
          <template #value>
            <van-tag v-if="actor.new_work_count > 0" type="danger" round>
              {{ actor.new_work_count }}
            </van-tag>
          </template>
        </van-cell>
        <template #right>
          <van-button 
            square 
            type="danger" 
            text="取消订阅" 
            class="swipe-btn" 
            @click="unsubscribeActor(actor)" 
          />
        </template>
      </van-swipe-cell>
    </div>

    <van-popup v-model:show="showAddPopup" round position="bottom" :style="{ height: '40%' }">
      <div class="add-popup">
        <van-nav-bar title="添加订阅" left-text="取消" @click-left="showAddPopup = false">
          <template #right>
            <van-button type="primary" size="small" @click="addSubscription" :loading="subscribing">
              确定
            </van-button>
          </template>
        </van-nav-bar>
        <van-field
          v-model="newActorName"
          label="演员名称"
          placeholder="请输入演员名称"
        />
        <div class="search-hint">
          <van-button size="small" plain @click="searchActor" :loading="searching">
            搜索演员
          </van-button>
        </div>
        <div v-if="searchResults.length > 0" class="search-results">
          <van-cell 
            v-for="result in searchResults" 
            :key="result.actor_id"
            :title="result.actor_name"
            clickable
            @click="selectSearchResult(result)"
          />
        </div>
      </div>
    </van-popup>

    <van-popup v-model:show="showDetailPopup" round position="bottom" :style="{ height: '80%' }">
      <div class="detail-popup" v-if="selectedActor">
        <van-nav-bar :title="selectedActor.name" left-text="关闭" @click-left="closeDetailPopup">
          <template #right>
            <van-button type="primary" size="small" @click="loadWorks" :loading="loadingWorks">
              获取作品
            </van-button>
          </template>
        </van-nav-bar>

        <div v-if="works.length === 0 && !loadingWorks" class="empty-detail">
          <van-empty description="点击右上角'获取作品'按钮加载作品列表">
            <van-button type="primary" @click="loadWorks" :loading="loadingWorks">
              获取作品
            </van-button>
          </van-empty>
        </div>

        <div v-else class="works-container">
          <div class="works-list">
            <van-cell-group>
              <van-cell 
                v-for="work in works" 
                :key="work.video_id" 
                clickable
                @click="importWork(work)"
              >
                <template #title>
                  <div class="work-title">
                    <span class="work-code">{{ work.code }}</span>
                    <span class="title-text">{{ work.title }}</span>
                  </div>
                </template>
                <template #value>
                  <van-button size="small" type="primary" :loading="work.importing">
                    导入
                  </van-button>
                </template>
              </van-cell>
            </van-cell-group>
          </div>

          <div v-if="hasMore" class="load-more">
            <van-button block :loading="loadingWorks" @click="loadMore">
              加载更多
            </van-button>
          </div>
        </div>
      </div>
    </van-popup>

    <!-- 底部导航 - 手机端显示 -->
    <van-tabbar v-if="isMobile" v-model="active" route>
      <van-tabbar-item icon="home-o" :to="homePath">主页</van-tabbar-item>
      <van-tabbar-item icon="user-o" to="/actors">演员</van-tabbar-item>
      <van-tabbar-item icon="user-o" to="/mine">我的</van-tabbar-item>
    </van-tabbar>
    
    <!-- 顶部导航 - 电脑端显示 -->
    <div v-if="isDesktop" class="desktop-nav">
      <router-link :to="homePath" class="nav-item" :class="{ active: $route.path === '/' || $route.path === '/video-home' }">
        <van-icon name="home-o" />
        <span>主页</span>
      </router-link>
      <router-link to="/actors" class="nav-item" :class="{ active: $route.path === '/actors' }">
        <van-icon name="user-o" />
        <span>演员</span>
      </router-link>
      <router-link to="/mine" class="nav-item" :class="{ active: $route.path === '/mine' }">
        <van-icon name="user-o" />
        <span>我的</span>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { useActorStore, useVideoStore, useModeStore } from '@/stores'
import { useDevice } from '@/composables/useDevice'
import { videoApi, actorApi } from '@/api/video'

const route = useRoute()
const actorStore = useActorStore()
const videoStore = useVideoStore()
const modeStore = useModeStore()
const { isDesktop, isMobile } = useDevice()

const homePath = computed(() => modeStore.isVideoMode ? '/video-home' : '/')

const loading = ref(false)
const actors = ref([])
const showAddPopup = ref(false)
const newActorName = ref('')
const subscribing = ref(false)
const searching = ref(false)
const searchResults = ref([])
const showDetailPopup = ref(false)
const selectedActor = ref(null)
const works = ref([])
const loadingWorks = ref(false)
const hasMore = ref(false)
const currentPage = ref(1)
const active = ref(1)

async function loadActors() {
  loading.value = true
  await actorStore.fetchList()
  actors.value = actorStore.actors
  loading.value = false
}

async function addSubscription() {
  if (!newActorName.value.trim()) {
    showFailToast('请输入演员名称')
    return
  }
  
  subscribing.value = true
  const result = await actorStore.subscribe(newActorName.value.trim())
  subscribing.value = false
  
  if (result.success) {
    showSuccessToast('订阅成功')
    newActorName.value = ''
    showAddPopup.value = false
    await loadActors()
  } else {
    showFailToast(result.message || '订阅失败')
  }
}

async function searchActor() {
  if (!newActorName.value.trim()) {
    return
  }
  
  searching.value = true
  try {
    const res = await videoApi.thirdPartyActorSearch(newActorName.value.trim())
    if (res.code === 200) {
      searchResults.value = res.data || []
    }
  } catch (e) {
    showFailToast('搜索失败')
  } finally {
    searching.value = false
  }
}

function selectSearchResult(result) {
  newActorName.value = result.actor_name
  searchResults.value = []
}

async function unsubscribeActor(actor) {
  try {
    await showConfirmDialog({
      title: '确认操作',
      message: `确定取消订阅 ${actor.name} 吗？`
    })
    
    const success = await actorStore.unsubscribe(actor.id)
    if (success) {
      showSuccessToast('已取消订阅')
      await loadActors()
    } else {
      showFailToast('操作失败')
    }
  } catch (e) {
    // 取消操作
  }
}

function showActorDetail(actor) {
  selectedActor.value = actor
  works.value = []
  currentPage.value = 1
  hasMore.value = false
  showDetailPopup.value = true
}

function closeDetailPopup() {
  showDetailPopup.value = false
  selectedActor.value = null
}

async function loadWorks() {
  if (!selectedActor.value?.actor_id) {
    showFailToast('该演员没有关联的第三方ID')
    return
  }
  
  loadingWorks.value = true
  try {
    const res = await videoApi.thirdPartyActorWorks(selectedActor.value.actor_id, currentPage.value)
    if (res.code === 200) {
      const data = res.data
      const newWorks = (data.works || []).map(w => ({ ...w, importing: false }))
      works.value = currentPage.value === 1 ? newWorks : [...works.value, ...newWorks]
      hasMore.value = data.has_next
    }
  } catch (e) {
    showFailToast('获取作品失败')
  } finally {
    loadingWorks.value = false
  }
}

async function loadMore() {
  currentPage.value++
  await loadWorks()
}

async function importWork(work) {
  work.importing = true
  try {
    const res = await videoStore.thirdPartyImport(work.video_id)
    if (res.code === 200) {
      showSuccessToast('导入成功')
    } else {
      showFailToast(res.msg || '导入失败')
    }
  } catch (e) {
    showFailToast('导入失败')
  } finally {
    work.importing = false
  }
}

onMounted(() => {
  modeStore.setMode('video')
  loadActors()
})
</script>

<style scoped>
.actor-page {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 50px;
}

.loading-center {
  display: flex;
  justify-content: center;
  padding-top: 100px;
}

.actor-list {
  background: #fff;
}

.actor-cell {
  display: flex;
  flex-direction: column;
}

.actor-name {
  font-size: 16px;
  font-weight: 500;
  color: #333;
}

.new-badge {
  font-size: 12px;
  color: #ee0a24;
  margin-left: 8px;
}

.actor-status {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.swipe-btn {
  height: 100%;
}

.add-popup {
  padding-bottom: 20px;
}

.search-hint {
  padding: 10px 16px;
}

.search-results {
  max-height: 200px;
  overflow-y: auto;
}

.detail-popup {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.empty-detail {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.works-container {
  flex: 1;
  overflow-y: auto;
}

.works-list {
  padding: 10px;
}

.work-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.work-code {
  font-size: 12px;
  color: #1989fa;
  background: #e8f4ff;
  padding: 2px 6px;
  border-radius: 4px;
}

.title-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.load-more {
  padding: 10px;
}

.actor-page-mobile {
  padding-bottom: 50px;
}

.actor-page-desktop {
  max-width: 1400px;
  margin: 0 auto;
}

.desktop-nav {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  background: #fff;
  border-radius: 50px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  display: flex;
  padding: 8px 20px;
  gap: 30px;
  z-index: 1000;
}

.desktop-nav .nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  text-decoration: none;
  color: #666;
  font-size: 12px;
  transition: all 0.3s;
}

.desktop-nav .nav-item:hover {
  color: #1989fa;
}

.desktop-nav .nav-item.active {
  color: #1989fa;
}

.desktop-nav .nav-item .van-icon {
  font-size: 22px;
}
</style>
