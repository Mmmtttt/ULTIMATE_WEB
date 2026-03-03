<template>
  <div class="author-page">
    <van-nav-bar title="作者" left-text="返回" left-arrow @click-left="$router.back()">
      <template #right>
        <van-icon name="plus" @click="showAddPopup = true" />
        <van-icon 
          v-if="subscribedAuthors.length > 0" 
          :name="reorderMode ? 'success' : 'exchange'" 
          @click="toggleReorderMode" 
          :class="{ 'reorder-active': reorderMode }"
        />
      </template>
    </van-nav-bar>

    <van-loading v-if="isLoading" type="spinner" color="#1989fa" class="loading-center" />

    <div v-else-if="allAuthors.length === 0" class="empty">
      <van-empty description="暂无作者" />
    </div>

    <div v-else class="author-list">
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <van-swipe-cell v-for="author in allAuthors" :key="author.name">
          <van-cell 
            :is-link="!reorderMode || !author.is_subscribed"
            @click="reorderMode && author.is_subscribed ? null : showAuthorDetail(author)"
            :class="{ 'subscribed-author': author.is_subscribed, 'reorder-item': reorderMode && author.is_subscribed }"
          >
            <template #title>
              <div class="author-cell-title">
                <div class="author-cell">
                  <div class="author-main">
                    <div class="author-name">
                      {{ author.name }}
                      <span v-if="author.is_subscribed" class="subscribed-tag">已订阅</span>
                    </div>
                    <div class="author-status">
                      <span v-if="author.subscription && author.subscription.new_work_count > 0" class="new-badge">
                        {{ author.subscription.new_work_count }} 个新作品
                      </span>
                      <span v-else-if="author.subscription && author.subscription.last_work_title" class="last-work">
                        最新: {{ author.subscription.last_work_title }}
                      </span>
                      <span v-else class="last-work">暂无作品记录</span>
                    </div>
                  </div>
                  <div v-if="reorderMode && author.is_subscribed" class="reorder-btns" @click.stop>
                    <van-icon name="arrow-up" @click="moveAuthor(author, -1)" :disabled="getAuthorOrder(author) === 0" />
                    <van-icon name="arrow-down" @click="moveAuthor(author, 1)" :disabled="getAuthorOrder(author) >= subscribedAuthors.length - 1" />
                  </div>
                  <van-tag v-else-if="author.subscription && author.subscription.new_work_count > 0" type="danger" round>
                    {{ author.subscription.new_work_count }}
                  </van-tag>
                </div>
              </div>
            </template>
          </van-cell>
          <template #right>
            <van-button 
              v-if="author.is_subscribed"
              square 
              type="danger" 
              text="取消订阅" 
              class="swipe-btn" 
              @click="confirmUnsubscribe(author.subscription)" 
            />
            <van-button 
              v-else
              square 
              type="primary" 
              text="订阅" 
              class="swipe-btn" 
              @click="subscribeAuthor(author.name)" 
            />
          </template>
        </van-swipe-cell>
      </van-pull-refresh>
    </div>

    <div class="check-all-btn" v-if="subscribedAuthors.length > 0">
      <van-button type="primary" block :loading="checking" @click="checkAllAuthors">
        检查所有订阅作者更新 ({{ subscribedAuthors.length }})
      </van-button>
    </div>

    <van-popup v-model:show="showAddPopup" round position="bottom" :style="{ height: '30%' }">
      <div class="add-popup">
        <van-nav-bar title="添加订阅" left-text="取消" @click-left="showAddPopup = false">
          <template #right>
            <van-button type="primary" size="small" @click="addSubscription">确定</van-button>
          </template>
        </van-nav-bar>
        <van-field
          v-model="newAuthorName"
          label="作者名称"
          placeholder="请输入作者名称"
          :rules="[{ required: true, message: '请输入作者名称' }]"
        />
      </div>
    </van-popup>

    <van-popup v-model:show="showDetailPopup" round position="bottom" :style="{ height: '80%' }">
      <div class="detail-popup" v-if="selectedAuthor">
        <van-nav-bar :title="selectedAuthor.name" left-text="关闭" @click-left="closeDetailPopup">
          <template #right>
            <van-dropdown-menu>
              <van-dropdown-item title="跳转" @change="onJumpChange">
                <van-cell title="主页" clickable @click="jumpToHomepage" />
                <van-cell title="推荐页" clickable @click="jumpToRecommendation" />
              </van-dropdown-item>
            </van-dropdown-menu>
            <van-button 
              v-if="!selectedAuthor.is_subscribed"
              type="success" 
              size="small" 
              @click="subscribeSelectedAuthor"
              :loading="subscribing"
            >
              订阅
            </van-button>
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
          <div class="works-header">
            <van-checkbox v-model="selectAll" @change="toggleSelectAll">全选</van-checkbox>
            <span class="selected-count">已选 {{ selectedWorks.length }} 个</span>
          </div>

          <van-checkbox-group v-model="selectedIds" class="works-list">
            <van-cell-group>
              <van-cell v-for="work in works" :key="work.id" clickable @click="toggleSelect(work.id)">
                <template #title>
                  <div class="work-title">
                    <van-checkbox :name="work.id" @click.stop />
                    <span class="work-index">{{ work.backendIndex }}</span>
                    <div v-if="work.cover_url" class="work-cover">
                      <img :src="work.cover_url" :alt="work.title" @load="handleCoverLoad(work)" @error="handleCoverError(work)" ref="imgRef" />
                    </div>
                    <div class="work-content">
                      <span class="title-text">{{ work.title }}</span>
                      <div class="work-info">
                        <span v-if="work.has_detail">{{ work.author || '' }}</span>
                        <van-loading v-else-if="loadingDetailIds.includes(work.id)" size="12" />
                        <span v-else class="loading-hint">等待加载详情...</span>
                      </div>
                    </div>
                  </div>
                </template>
                <template #value>
                  <span v-if="work.pages > 0" class="work-pages">{{ work.pages }}页</span>
                </template>
              </van-cell>
            </van-cell-group>
          </van-checkbox-group>

          <div v-if="hasMore" class="load-more">
            <van-button block :loading="loadingWorks" @click="loadMore">
              加载更多 ({{ actualFetchedCount }}/{{ totalWorks }})
            </van-button>
          </div>

          <div class="import-btn-section">
            <van-button type="primary" block :disabled="selectedWorks.length === 0" @click="showImportOptions = true">
              导入选中的 {{ selectedWorks.length }} 个作品
            </van-button>
          </div>
        </div>
      </div>
    </van-popup>

    <van-action-sheet v-model:show="showImportOptions" title="选择导入位置">
      <div class="import-options">
        <van-button type="primary" block @click="importToHomepage">
          导入到主页
        </van-button>
        <van-button type="success" block @click="importToRecommendation">
          导入到推荐页
        </van-button>
      </div>
    </van-action-sheet>

    <van-tabbar v-model="active" route>
      <van-tabbar-item icon="home-o" to="/">主页</van-tabbar-item>
      <van-tabbar-item icon="star-o" to="/recommendation">推荐</van-tabbar-item>
      <van-tabbar-item icon="user-o" to="/mine">我的</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { authorApi } from '@/api'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { useCacheStore } from '@/stores'

const router = useRouter()
const cacheStore = useCacheStore()
const active = ref(1)
const isLoading = ref(true)
const refreshing = ref(false)
const checking = ref(false)
const subscribing = ref(false)
const loadingWorks = ref(false)
const allAuthors = ref([])
const showAddPopup = ref(false)
const showDetailPopup = ref(false)
const showImportOptions = ref(false)
const newAuthorName = ref('')
const selectedAuthor = ref(null)
const works = ref([])
const selectedIds = ref([])
const totalWorks = ref(0)
const currentOffset = ref(0)
const hasMore = ref(false)
const loadingDetailIds = ref([])
const coverCheckTimers = ref({})
const actualFetchedCount = ref(0)
const reorderMode = ref(false)

const subscribedAuthors = computed(() => {
  return allAuthors.value.filter(a => a.is_subscribed)
})

const selectedWorks = computed(() => {
  return works.value.filter(w => selectedIds.value.includes(w.id))
})

const selectAll = computed({
  get: () => selectedIds.value.length === works.value.length && works.value.length > 0,
  set: () => {}
})

function getStoredAuthorOrder() {
  try {
    const stored = localStorage.getItem('author_order')
    return stored ? JSON.parse(stored) : {}
  } catch {
    return {}
  }
}

function sortAuthors(authors) {
  const orderMap = getStoredAuthorOrder()
  
  return [...authors].sort((a, b) => {
    const aSubscribed = a.is_subscribed ? 1 : 0
    const bSubscribed = b.is_subscribed ? 1 : 0
    
    if (aSubscribed !== bSubscribed) {
      return bSubscribed - aSubscribed
    }
    
    if (aSubscribed && bSubscribed) {
      const aOrder = orderMap[a.subscription?.id] ?? orderMap[a.name] ?? 999
      const bOrder = orderMap[b.subscription?.id] ?? orderMap[b.name] ?? 999
      return aOrder - bOrder
    }
    
    return a.name.localeCompare(b.name)
  })
}

async function fetchAuthors(forceRefresh = false) {
  if (!forceRefresh) {
    const cached = cacheStore.getAuthorsCache()
    if (cached) {
      allAuthors.value = sortAuthors(cached)
      return
    }
  }
  
  try {
    const response = await authorApi.getAllAuthors()
    if (response.code === 200) {
      const authors = response.data || []
      allAuthors.value = sortAuthors(authors)
      cacheStore.setAuthorsCache(authors)
    }
  } catch (error) {
    console.error('获取作者列表失败:', error)
    showFailToast('获取作者列表失败')
  }
}

async function onRefresh() {
  await fetchAuthors(true)
  refreshing.value = false
}

async function addSubscription() {
  if (!newAuthorName.value.trim()) {
    showFailToast('请输入作者名称')
    return
  }

  try {
    const response = await authorApi.subscribe(newAuthorName.value.trim())
    if (response.code === 200) {
      showSuccessToast('订阅成功')
      showAddPopup.value = false
      newAuthorName.value = ''
      cacheStore.clearAuthorsCache()
      await fetchAuthors(true)
    } else {
      showFailToast(response.msg || '订阅失败')
    }
  } catch (error) {
    console.error('订阅作者失败:', error)
    showFailToast('订阅失败')
  }
}

async function subscribeAuthor(name) {
  try {
    const response = await authorApi.subscribe(name)
    if (response.code === 200) {
      showSuccessToast('订阅成功')
      cacheStore.clearAuthorsCache()
      await fetchAuthors(true)
    } else {
      showFailToast(response.msg || '订阅失败')
    }
  } catch (error) {
    console.error('订阅作者失败:', error)
    showFailToast('订阅失败')
  }
}

async function subscribeSelectedAuthor() {
  if (!selectedAuthor.value) return
  
  subscribing.value = true
  try {
    const response = await authorApi.subscribe(selectedAuthor.value.name)
    if (response.code === 200) {
      showSuccessToast('订阅成功')
      cacheStore.clearAuthorsCache()
      await fetchAuthors(true)
      const author = allAuthors.value.find(a => a.name === selectedAuthor.value.name)
      if (author) {
        selectedAuthor.value = author
      }
    } else {
      showFailToast(response.msg || '订阅失败')
    }
  } catch (error) {
    console.error('订阅作者失败:', error)
    showFailToast('订阅失败')
  } finally {
    subscribing.value = false
  }
}

async function confirmUnsubscribe(author) {
  try {
    await showConfirmDialog({
      title: '确认取消订阅',
      message: `确定要取消订阅"${author.name}"吗？`,
    })
    await unsubscribe(author.id)
  } catch {
  }
}

async function unsubscribe(authorId) {
  try {
    const response = await authorApi.unsubscribe(authorId)
    if (response.code === 200) {
      showSuccessToast('已取消订阅')
      cacheStore.clearAuthorsCache()
      await fetchAuthors(true)
    } else {
      showFailToast(response.msg || '取消订阅失败')
    }
  } catch (error) {
    console.error('取消订阅失败:', error)
    showFailToast('取消订阅失败')
  }
}

async function checkAllAuthors() {
  checking.value = true
  try {
    const response = await authorApi.checkUpdates()
    if (response.code === 200) {
      const data = response.data
      if (data.total_new_works > 0) {
        showSuccessToast(`发现 ${data.total_new_works} 个新作品`)
      } else {
        showSuccessToast('暂无新作品')
      }
      cacheStore.clearAuthorsCache()
      await fetchAuthors(true)
    } else {
      showFailToast(response.msg || '检查更新失败')
    }
  } catch (error) {
    console.error('检查更新失败:', error)
    showFailToast('检查更新失败')
  } finally {
    checking.value = false
  }
}

function toggleReorderMode() {
  if (reorderMode.value) {
    const orderMap = getStoredAuthorOrder()
    subscribedAuthors.value.forEach((author, index) => {
      const key = author.subscription?.id || author.name
      orderMap[key] = index
    })
    localStorage.setItem('author_order', JSON.stringify(orderMap))
    showSuccessToast('排序已保存')
  }
  reorderMode.value = !reorderMode.value
}

function onJumpChange() {}

function jumpToHomepage() {
  closeDetailPopup()
  router.push({ path: '/', query: { author: selectedAuthor.value.name } })
}

function jumpToRecommendation() {
  closeDetailPopup()
  router.push({ path: '/recommendation', query: { author: selectedAuthor.value.name } })
}

function getAuthorOrder(author) {
  const index = subscribedAuthors.value.findIndex(a => a.name === author.name)
  return index
}

function moveAuthor(author, direction) {
  const currentOrder = getStoredAuthorOrder()
  const key = author.subscription?.id || author.name
  const currentIndex = subscribedAuthors.value.findIndex(a => a.name === author.name)
  const newIndex = currentIndex + direction
  
  if (newIndex < 0 || newIndex >= subscribedAuthors.value.length) return
  
  const otherAuthor = subscribedAuthors.value[newIndex]
  const otherKey = otherAuthor.subscription?.id || otherAuthor.name
  
  currentOrder[key] = newIndex
  currentOrder[otherKey] = currentIndex
  
  localStorage.setItem('author_order', JSON.stringify(currentOrder))
  
  allAuthors.value = sortAuthors(allAuthors.value)
}

async function showAuthorDetail(author) {
  selectedAuthor.value = author
  showDetailPopup.value = true
  
  if (author.is_subscribed && author.subscription && author.subscription.new_work_count > 0) {
    await authorApi.clearNewCount(author.subscription.id)
    author.subscription.new_work_count = 0
    
    const authorIndex = allAuthors.value.findIndex(a => 
      a.is_subscribed && a.subscription && a.subscription.id === author.subscription.id
    )
    if (authorIndex !== -1) {
      allAuthors.value[authorIndex].subscription.new_work_count = 0
    }
  }
  
  const cacheKey = author.is_subscribed && author.subscription ? author.subscription.id : author.name
  const cachedWorks = cacheStore.getAuthorWorksCache(cacheKey)
  
  if (cachedWorks && cachedWorks.length > 0) {
    works.value = cachedWorks
    selectedIds.value = []
    totalWorks.value = cachedWorks.length
    currentOffset.value = cachedWorks.length
    actualFetchedCount.value = cachedWorks.length
    hasMore.value = false
    return
  }
  
  works.value = []
  selectedIds.value = []
  totalWorks.value = 0
  currentOffset.value = 0
  actualFetchedCount.value = 0
  hasMore.value = true
  
  await loadMoreFromServer()
}

async function loadMoreFromServer() {
  loadingWorks.value = true
  try {
    let response
    
    if (selectedAuthor.value.is_subscribed && selectedAuthor.value.subscription) {
      response = await authorApi.getWorks(selectedAuthor.value.subscription.id, actualFetchedCount.value, 5)
    } else {
      response = await authorApi.searchWorksByName(selectedAuthor.value.name, actualFetchedCount.value, 5)
    }
    
    if (response.code === 200) {
      const data = response.data
      
      if (data.from_cache && data.works && data.works.length > 0 && works.value.length === 0) {
        works.value = data.works.map((work, index) => ({
          ...work,
          backendIndex: data.offset + index + 1
        }))
        selectedIds.value = []
        totalWorks.value = data.total
        actualFetchedCount.value = data.works.length
        hasMore.value = data.has_more
        
        const cacheKey = selectedAuthor.value.is_subscribed && selectedAuthor.value.subscription 
          ? selectedAuthor.value.subscription.id 
          : selectedAuthor.value.name
        cacheStore.setAuthorWorksCache(cacheKey, works.value)
        return
      }
      
      const worksWithLocalCover = data.works.map((work, index) => {
        return {
          ...work,
          backendIndex: data.offset + index + 1
        }
      })
      
      const existingWorks = works.value
      works.value = [...existingWorks, ...worksWithLocalCover]
      totalWorks.value = data.total
      actualFetchedCount.value = data.offset + data.limit
      hasMore.value = data.has_more
      
      const cacheKey = selectedAuthor.value.is_subscribed && selectedAuthor.value.subscription 
        ? selectedAuthor.value.subscription.id 
        : selectedAuthor.value.name
      cacheStore.setAuthorWorksCache(cacheKey, works.value)
      
      worksWithLocalCover.forEach(work => {
        if (!work.cover_url.startsWith('http')) return
        
        const localCoverUrl = `/static/cover/JM/author_cache/${work.id}.jpg?t=${Date.now()}`
        
        const checkLocalCache = () => {
          const idx = works.value.findIndex(w => w.id === work.id)
          if (idx !== -1) {
            works.value[idx].cover_url = localCoverUrl
          }
        }
        
        fetch(localCoverUrl, { method: 'GET', cache: 'no-store' })
          .then(res => {
            if (res.ok) checkLocalCache()
          })
          .catch(() => {})
      })
      
      loadDetailsAsync(data.works.map(w => w.id))
    } else {
      showFailToast(response.msg || '获取作品失败')
    }
  } catch (error) {
    console.error('获取作品失败:', error)
    showFailToast('获取作品失败')
  } finally {
    loadingWorks.value = false
  }
}

function closeDetailPopup() {
  showDetailPopup.value = false
  Object.values(coverCheckTimers.value).forEach(timer => clearInterval(timer))
  coverCheckTimers.value = {}
}

function handleCoverLoad(work) {
  if (!work.cover_url.startsWith('http')) return;
  
  checkLocalCoverFirst(work);
}

function handleCoverError(work) {
  if (!work.cover_url.startsWith('http')) return;
  
  checkLocalCoverFirst(work);
}

function checkLocalCoverFirst(work) {
  if (!work.original_cover_url) {
    work.original_cover_url = work.cover_url;
  }
  
  const localCoverUrl = `/static/cover/JM/author_cache/${work.id}.jpg`;
  
  const tempImg = new Image();
  tempImg.onload = () => {
    work.cover_url = localCoverUrl + '?t=' + Date.now();
  };
  tempImg.onerror = () => {
    // Remote cover already showing, start background check for local cache
    startCoverCheck(work);
  };
  tempImg.src = localCoverUrl + '?t=' + Date.now();
}

function startCoverCheck(work) {
  if (coverCheckTimers.value[work.id]) return
  
  if (!work.original_cover_url) {
    work.original_cover_url = work.cover_url
  }
  
  const localCoverUrl = `/static/cover/JM/author_cache/${work.id}.jpg`
  const MAX_RETRIES = 30;
  let checkCount = 0;
  
  coverCheckTimers.value[work.id] = setInterval(() => {
    checkCount++;
    
    // Stop checking if work no longer exists in the list
    const workExists = works.value.some(w => w.id === work.id);
    if (!workExists) {
      clearInterval(coverCheckTimers.value[work.id]);
      delete coverCheckTimers.value[work.id];
      return;
    }
    
    try {
      const tempImg = new Image();
      // Set timeout to avoid hanging image requests
      const timeoutId = setTimeout(() => {
        tempImg.src = '';
        if (checkCount >= MAX_RETRIES) {
          clearInterval(coverCheckTimers.value[work.id]);
          delete coverCheckTimers.value[work.id];
        }
      }, 2000);
      
      tempImg.onload = () => {
        clearTimeout(timeoutId);
        clearInterval(coverCheckTimers.value[work.id]);
        delete coverCheckTimers.value[work.id];
        
        const index = works.value.findIndex(w => w.id === work.id);
        if (index !== -1) {
          works.value[index].cover_url = localCoverUrl + '?t=' + Date.now();
        }
      };
      
      tempImg.onerror = () => {
        clearTimeout(timeoutId);
        if (checkCount >= MAX_RETRIES) {
          clearInterval(coverCheckTimers.value[work.id]);
          delete coverCheckTimers.value[work.id];
        }
      };
      
      tempImg.src = localCoverUrl + '?t=' + Date.now();
    } catch (error) {
      console.error(`Error checking cover for work ${work.id}:`, error);
      if (checkCount >= MAX_RETRIES) {
        clearInterval(coverCheckTimers.value[work.id]);
        delete coverCheckTimers.value[work.id];
      }
    }
  }, 500)
}

async function loadWorks() {
  works.value = []
  selectedIds.value = []
  totalWorks.value = 0
  currentOffset.value = 0
  actualFetchedCount.value = 0
  hasMore.value = true
  
  const cacheKey = selectedAuthor.value.is_subscribed && selectedAuthor.value.subscription 
    ? selectedAuthor.value.subscription.id 
    : selectedAuthor.value.name
  
  try {
    await authorApi.clearWorksCache(selectedAuthor.value.name)
  } catch (e) {
    console.error('清除缓存失败:', e)
  }
  
  cacheStore.clearAuthorWorksCache(cacheKey)
  
  await loadMoreFromServer()
}

async function loadMore() {
  await loadMoreFromServer()
}

function loadDetailsAsync(ids) {
  const idsToLoad = ids.filter(id => {
    const work = works.value.find(w => w.id === id)
    return work && !work.has_detail
  })
  
  if (idsToLoad.length === 0) return
  
  loadingDetailIds.value = [...loadingDetailIds.value, ...idsToLoad]
  
  authorApi.getWorksBatchDetail(idsToLoad)
    .then(response => {
      if (response.code === 200) {
        const detailWorks = response.data.works
        const worksToRemove = []
        
        detailWorks.forEach(detailWork => {
          const index = works.value.findIndex(w => w.id === detailWork.id)
          if (index !== -1) {
            const existingCoverUrl = works.value[index].cover_url
            works.value[index] = { ...works.value[index], ...detailWork }
            works.value[index].cover_url = existingCoverUrl
            
            if (selectedAuthor.value && detailWork.author) {
              if (detailWork.author.trim().toLowerCase() !== selectedAuthor.value.name.trim().toLowerCase()) {
                worksToRemove.push(detailWork.id)
              }
            }
          }
        })
        
        worksToRemove.forEach(id => {
          const index = works.value.findIndex(w => w.id === id)
          if (index !== -1) {
            works.value.splice(index, 1)
          }
          
          const idIndex = selectedIds.value.indexOf(id)
          if (idIndex !== -1) {
            selectedIds.value.splice(idIndex, 1)
          }
        })
      }
    })
    .catch(error => {
      console.error('获取详情失败:', error)
    })
    .finally(() => {
      loadingDetailIds.value = loadingDetailIds.value.filter(id => !idsToLoad.includes(id))
    })
}

function toggleSelect(workId) {
  const index = selectedIds.value.indexOf(workId)
  if (index === -1) {
    selectedIds.value.push(workId)
  } else {
    selectedIds.value.splice(index, 1)
  }
}

function toggleSelectAll(checked) {
  if (checked) {
    selectedIds.value = works.value.map(w => w.id)
  } else {
    selectedIds.value = []
  }
}

function showImportOptionsSheet() {
  if (selectedWorks.value.length === 0) {
    showFailToast('请先选择要导入的作品')
    return
  }
  showImportOptions.value = true
}

function importToHomepage() {
  showImportOptions.value = false
  const ids = selectedWorks.value.map(w => w.id).join(',')
  router.push(`/?importIds=${ids}`)
  showDetailPopup.value = false
}

function importToRecommendation() {
  showImportOptions.value = false
  const ids = selectedWorks.value.map(w => w.id).join(',')
  router.push(`/recommendation?importIds=${ids}`)
  showDetailPopup.value = false
}

onMounted(async () => {
  await fetchAuthors()
  isLoading.value = false
})
</script>

<style scoped>
.author-page {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 100px;
}

.loading-center {
  display: flex;
  justify-content: center;
  padding: 100px 0;
}

.empty {
  padding: 100px 20px;
}

.author-list {
  background: #fff;
}

.author-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.author-cell-title {
  width: 100%;
  flex: 1;
}

:deep(.van-cell__title) {
  flex: 1;
  max-width: 100%;
}

:deep(.van-cell__value) {
  display: none;
}

.author-cell {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 8px 0;
}

.author-main {
  flex: 1;
  min-width: 0;
  margin-right: 16px;
}

.author-name {
  font-size: 16px;
  font-weight: 500;
  color: #323233;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.author-status {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.new-badge {
  color: #ee0a24;
  font-size: 12px;
}

.last-work {
  color: #969799;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 300px;
}

.subscribed-tag {
  display: inline-block;
  padding: 2px 8px;
  background: #07c160;
  color: #fff;
  font-size: 10px;
  border-radius: 4px;
}

.reorder-active {
  color: #07c160;
  margin-left: 10px;
}

.reorder-item {
  cursor: default;
}

.reorder-btns {
  display: flex;
  gap: 8px;
}

.reorder-btns .van-icon {
  font-size: 18px;
  color: #1989fa;
}

.reorder-btns .van-icon[disabled] {
  color: #ccc;
}

.subscribed-author {
  background: linear-gradient(90deg, rgba(7, 193, 96, 0.08) 0%, rgba(7, 193, 96, 0) 100%);
}

.swipe-btn {
  height: 100%;
}

.check-all-btn {
  padding: 16px;
  position: fixed;
  bottom: 60px;
  left: 0;
  right: 0;
  background: #fff;
  box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.1);
}

.add-popup {
  padding-bottom: 20px;
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
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.works-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f7f8fa;
  border-bottom: 1px solid #ebedf0;
}

.selected-count {
  font-size: 12px;
  color: #969799;
}

.works-list {
  flex: 1;
  overflow-y: auto;
}

.work-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.work-index {
  font-size: 14px;
  font-weight: bold;
  color: #1989fa;
  min-width: 28px;
  text-align: center;
}

.work-cover {
  width: 60px;
  height: 80px;
  flex-shrink: 0;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f5f5;
}

.work-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.work-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.title-text {
  font-size: 14px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.work-info {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #969799;
}

.loading-hint {
  color: #969799;
  font-size: 12px;
}

.work-pages {
  font-size: 12px;
  color: #969799;
}

.load-more {
  padding: 12px 16px;
  border-top: 1px solid #ebedf0;
}

.import-btn-section {
  padding: 16px;
  background: #fff;
  border-top: 1px solid #eee;
}

.import-options {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
</style>
