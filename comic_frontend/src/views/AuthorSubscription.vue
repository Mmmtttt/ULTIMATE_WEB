<template>
  <div class="author-subscription">
    <van-nav-bar title="作者订阅" left-text="返回" left-arrow @click-left="$router.back()">
      <template #right>
        <van-icon name="plus" @click="showAddPopup = true" />
      </template>
    </van-nav-bar>

    <van-loading v-if="isLoading" type="spinner" color="#1989fa" class="loading-center" />

    <div v-else-if="authors.length === 0" class="empty">
      <van-empty description="暂无订阅作者">
        <van-button type="primary" @click="showAddPopup = true">添加订阅</van-button>
      </van-empty>
    </div>

    <div v-else class="author-list">
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <van-swipe-cell v-for="author in authors" :key="author.id">
          <van-cell :title="author.name" is-link @click="showAuthorDetail(author)">
            <template #label>
              <div class="author-info">
                <span v-if="author.new_work_count > 0" class="new-badge">
                  {{ author.new_work_count }} 个新作品
                </span>
                <span v-else-if="author.last_work_title" class="last-work">
                  最新: {{ author.last_work_title }}
                </span>
                <span v-else class="last-work">暂无作品记录</span>
              </div>
            </template>
            <template #value>
              <van-tag v-if="author.new_work_count > 0" type="danger" round>
                {{ author.new_work_count }}
              </van-tag>
            </template>
          </van-cell>
          <template #right>
            <van-button square type="danger" text="取消订阅" class="swipe-btn" @click="confirmUnsubscribe(author)" />
          </template>
        </van-swipe-cell>
      </van-pull-refresh>
    </div>

    <div class="check-all-btn" v-if="authors.length > 0">
      <van-button type="primary" block :loading="checking" @click="checkAllAuthors">
        检查所有作者更新
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
                    <span class="title-text">{{ work.title }}</span>
                  </div>
                </template>
                <template #label>
                  <div class="work-info">
                    <span v-if="work.has_detail">{{ work.author || '' }}</span>
                    <van-loading v-else-if="loadingDetailIds.includes(work.id)" size="12" />
                    <span v-else class="loading-hint">等待加载详情...</span>
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
              加载更多 ({{ works.length }}/{{ totalWorks }})
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

const router = useRouter()
const active = ref(1)
const isLoading = ref(true)
const refreshing = ref(false)
const checking = ref(false)
const loadingWorks = ref(false)
const authors = ref([])
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

const selectedWorks = computed(() => {
  return works.value.filter(w => selectedIds.value.includes(w.id))
})

const selectAll = computed({
  get: () => selectedIds.value.length === works.value.length && works.value.length > 0,
  set: () => {}
})

async function fetchAuthors() {
  try {
    const response = await authorApi.getList()
    if (response.code === 200) {
      authors.value = response.data || []
    }
  } catch (error) {
    console.error('获取作者列表失败:', error)
    showFailToast('获取作者列表失败')
  }
}

async function onRefresh() {
  await fetchAuthors()
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
      await fetchAuthors()
    } else {
      showFailToast(response.msg || '订阅失败')
    }
  } catch (error) {
    console.error('订阅作者失败:', error)
    showFailToast('订阅失败')
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
    // 用户取消
  }
}

async function unsubscribe(authorId) {
  try {
    const response = await authorApi.unsubscribe(authorId)
    if (response.code === 200) {
      showSuccessToast('已取消订阅')
      await fetchAuthors()
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
      await fetchAuthors()
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

function showAuthorDetail(author) {
  selectedAuthor.value = author
  showDetailPopup.value = true
  works.value = []
  selectedIds.value = []
  totalWorks.value = 0
  currentOffset.value = 0
  hasMore.value = false
}

function closeDetailPopup() {
  showDetailPopup.value = false
}

async function loadWorks() {
  await loadMore()
}

async function loadMore() {
  loadingWorks.value = true
  try {
    const response = await authorApi.getWorks(selectedAuthor.value.id, currentOffset.value, 5)
    if (response.code === 200) {
      const data = response.data
      works.value = [...works.value, ...data.works]
      totalWorks.value = data.total
      currentOffset.value = data.offset + data.limit
      hasMore.value = data.has_more
      
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
        detailWorks.forEach(detailWork => {
          const index = works.value.findIndex(w => w.id === detailWork.id)
          if (index !== -1) {
            works.value[index] = { ...works.value[index], ...detailWork }
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
.author-subscription {
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

.new-badge {
  color: #ee0a24;
  font-size: 12px;
}

.last-work {
  color: #969799;
  font-size: 12px;
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

.title-text {
  flex: 1;
}

.work-info {
  display: flex;
  align-items: center;
  gap: 4px;
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
