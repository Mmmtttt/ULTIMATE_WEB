<template>
  <div class="subscription-list-page">
    <div class="header-actions">
      <van-search 
        v-model="searchKeyword" 
        placeholder="搜索已订阅..." 
        shape="round"
        background="transparent"
      />
      <div class="header-buttons">
        <van-button 
          type="default" 
          size="small" 
          round 
          :loading="checkingUpdates"
          @click="checkAllUpdates"
        >
          检查更新
        </van-button>
        <van-button icon="plus" type="primary" size="small" round @click="showAddPopup = true">
          添加
        </van-button>
      </div>
    </div>

    <!-- Content -->
    <div class="content-area">
      <van-loading v-if="loading" class="loading-center" />
      
      <EmptyState 
        v-else-if="filteredItems.length === 0" 
        title="暂无订阅" 
        description="添加订阅以获取更新提醒"
      />

      <!-- Video Mode: Actor Grid -->
      <div v-else-if="isVideoMode" class="actor-grid">
        <div 
          v-for="actor in filteredItems" 
          :key="actor.id" 
          class="actor-card"
          @click="goToDetail(actor)"
        >
          <div class="actor-avatar">
            <!-- Placeholder for avatar if API provides one, currently using icon -->
            <van-icon name="user-circle-o" size="40" color="#ddd" />
            <div v-if="actor.new_work_count > 0" class="badge">{{ actor.new_work_count }}</div>
          </div>
          <div class="actor-name">{{ actor.name }}</div>
          <div class="actor-update">{{ actor.last_work_title || '暂无更新' }}</div>
        </div>
      </div>

      <!-- Comic Mode: Author List -->
      <div v-else class="author-list">
        <van-cell-group inset>
          <van-swipe-cell v-for="author in filteredItems" :key="author.id">
            <van-cell 
              :title="author.name" 
              :label="author.last_work_title || '暂无更新'"
              is-link
              @click="goToDetail(author)"
            >
              <template #value>
                <van-tag v-if="author.new_work_count > 0" type="danger" round>
                  {{ author.new_work_count }}
                </van-tag>
              </template>
            </van-cell>
            <template #right>
              <van-button square type="danger" text="取消订阅" @click="unsubscribe(author)" />
            </template>
          </van-swipe-cell>
        </van-cell-group>
      </div>
    </div>

    <!-- Add Subscription Popup -->
    <van-dialog 
      v-model:show="showAddPopup" 
      title="添加订阅" 
      show-cancel-button
      @confirm="addSubscription"
    >
      <van-field v-model="newSubscriptionName" label="名称" placeholder="输入作者/演员名称" />
    </van-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useModeStore, useActorStore, useAuthorStore } from '@/stores'
import EmptyState from '@/components/common/EmptyState.vue'
import { showToast, showConfirmDialog } from 'vant'

const router = useRouter()
const modeStore = useModeStore()
const actorStore = useActorStore()
const authorStore = useAuthorStore()

const loading = ref(false)
const items = ref([])
const searchKeyword = ref('')
const showAddPopup = ref(false)
const newSubscriptionName = ref('')
const checkingUpdates = ref(false)

const isVideoMode = computed(() => modeStore.isVideoMode)
const currentStore = computed(() => isVideoMode.value ? actorStore : authorStore)

const filteredItems = computed(() => {
  const safeItems = items.value || []
  if (!searchKeyword.value) return safeItems
  return safeItems.filter(item => 
    item.name?.toLowerCase().includes(searchKeyword.value.toLowerCase())
  )
})

async function loadData() {
  loading.value = true
  items.value = []
  
  try {
    await currentStore.value.fetchList()
    items.value = currentStore.value.actors || []
  } catch (e) {
    showToast('加载失败')
  } finally {
    loading.value = false
  }
}

async function checkAllUpdates() {
  if (checkingUpdates.value) return
  checkingUpdates.value = true
  try {
    const res = await currentStore.value.checkUpdates()
    if (res) {
      await loadData()
      const total = res?.total_new_works || 0
      if (total > 0) {
        showToast(`有 ${total} 个新作品`)
      } else {
        showToast('暂无新作品')
      }
    } else {
      showToast('检查更新失败')
    }
  } catch (e) {
    showToast('检查更新失败')
  } finally {
    checkingUpdates.value = false
  }
}

function goToDetail(item) {
  router.push(`/creator/${encodeURIComponent(item.name)}`)
}

async function addSubscription() {
  if (!newSubscriptionName.value) return
  
  try {
    const res = await currentStore.value.subscribe(newSubscriptionName.value)
    if (res.success) {
      showToast('订阅成功')
    } else {
      showToast(res.message || '订阅失败')
    }
    await loadData()
    newSubscriptionName.value = ''
  } catch (e) {
    showToast('操作失败')
  }
}

async function unsubscribe(item) {
  try {
    await showConfirmDialog({
      title: '确认取消订阅',
      message: `确定取消订阅 ${item.name} 吗？`
    })
    
    const subId = item.id
    await currentStore.value.unsubscribe(subId)
    showToast('已取消')
    await loadData()
  } catch (e) {
    // cancel
  }
}

watch(() => modeStore.currentMode, () => {
  loadData()
})

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.subscription-list-page {
  padding-bottom: 80px;
}

.header-actions {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  background: #fff;
  position: sticky;
  top: 0;
  z-index: 10;
}

.header-actions .van-search {
  flex: 1;
  padding: 0;
  margin-right: 12px;
}

.header-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
}

.loading-center {
  padding: 40px;
  text-align: center;
}

.actor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 16px;
  padding: 16px;
}

.actor-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  cursor: pointer;
}

.actor-avatar {
  position: relative;
  margin-bottom: 8px;
}

.badge {
  position: absolute;
  top: -4px;
  right: -4px;
  background: #ee0a24;
  color: #fff;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
  border: 2px solid #fff;
}

.actor-name {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}

.actor-update {
  font-size: 11px;
  color: #999;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
}

.author-list {
  padding-top: 12px;
}
</style>
