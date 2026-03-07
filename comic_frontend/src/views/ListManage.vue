<template>
  <div class="list-manage">
    <van-nav-bar
      title="清单管理"
      left-text="返回"
      left-arrow
      @click-left="$router.back()"
    >
      <template #right>
        <van-icon name="plus" size="18" @click="showCreateDialog = true" />
      </template>
    </van-nav-bar>
    
    <van-loading v-if="loading" class="loading-center" />
    
    <van-empty v-else-if="lists.length === 0" description="暂无清单" />
    
    <van-cell-group v-else inset class="list-group">
      <van-swipe-cell v-for="list in lists" :key="list.id">
        <van-cell
          :title="list.name"
          :label="list.desc || '暂无描述'"
          is-link
          @click="goToDetail(list.id)"
        >
          <template #value>
            <div class="list-counts">
              <van-badge v-if="list.content_type === 'comic'" :content="list.comic_count" :show-zero="false" class="count-badge">
                <van-icon name="photo-o" size="16" />
              </van-badge>
              <van-badge v-if="list.content_type === 'video'" :content="list.video_count" :show-zero="false" class="count-badge">
                <van-icon name="video-o" size="16" />
              </van-badge>
            </div>
          </template>
          <template #icon>
            <van-icon v-if="list.is_default" name="star" color="#ffd21e" size="16" class="list-icon" />
            <van-icon v-else name="list-switch" size="16" class="list-icon" />
          </template>
        </van-cell>
        <template #right v-if="!list.is_default">
          <van-button square type="primary" text="编辑" class="edit-btn" @click="openEditDialog(list)" />
          <van-button square type="danger" text="删除" @click="confirmDelete(list)" />
        </template>
      </van-swipe-cell>
    </van-cell-group>
    
    <van-popup v-model:show="showCreateDialog" round position="center">
      <div class="dialog-content">
        <h3>新建清单</h3>
        <van-field v-model="newListName" label="清单名称" placeholder="请输入清单名称" />
        <van-field v-model="newListDesc" label="清单描述" placeholder="请输入清单描述（可选）" />
        <div class="dialog-buttons">
          <van-button @click="showCreateDialog = false">取消</van-button>
          <van-button type="primary" @click="createList" :loading="creating">确定</van-button>
        </div>
      </div>
    </van-popup>
    
    <van-popup v-model:show="showEditDialog" round position="center">
      <div class="dialog-content">
        <h3>编辑清单</h3>
        <van-field v-model="editListName" label="清单名称" placeholder="请输入清单名称" />
        <van-field v-model="editListDesc" label="清单描述" placeholder="请输入清单描述（可选）" />
        <div class="dialog-buttons">
          <van-button @click="showEditDialog = false">取消</van-button>
          <van-button type="primary" @click="updateList" :loading="updating">确定</van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useListStore, useModeStore } from '@/stores'
import { showConfirmDialog, showSuccessToast, showFailToast } from 'vant'

const router = useRouter()
const listStore = useListStore()
const modeStore = useModeStore()

const loading = ref(false)
const creating = ref(false)
const updating = ref(false)
const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const newListName = ref('')
const newListDesc = ref('')
const editListName = ref('')
const editListDesc = ref('')
const editingListId = ref('')

const lists = ref([])

const currentContentType = computed(() => modeStore.isVideoMode ? 'video' : 'comic')

async function loadLists() {
  loading.value = true
  await listStore.fetchLists(currentContentType.value)
  lists.value = listStore.lists
  loading.value = false
}

function goToDetail(listId) {
  router.push(`/list/${listId}`)
}

function openEditDialog(list) {
  editingListId.value = list.id
  editListName.value = list.name
  editListDesc.value = list.desc || ''
  showEditDialog.value = true
}

async function createList() {
  if (!newListName.value.trim()) {
    showFailToast('请输入清单名称')
    return
  }
  
  creating.value = true
  const result = await listStore.createList(newListName.value.trim(), newListDesc.value.trim(), currentContentType.value)
  creating.value = false
  
  if (result) {
    showCreateDialog.value = false
    newListName.value = ''
    newListDesc.value = ''
    await loadLists()
  }
}

async function updateList() {
  if (!editListName.value.trim()) {
    showFailToast('请输入清单名称')
    return
  }
  
  updating.value = true
  const result = await listStore.updateList(
    editingListId.value,
    editListName.value.trim(),
    editListDesc.value.trim(),
    currentContentType.value
  )
  updating.value = false
  
  if (result) {
    showEditDialog.value = false
    await loadLists()
  }
}

async function confirmDelete(list) {
  showConfirmDialog({
    title: '删除清单',
    message: `确定要删除清单「${list.name}」吗？清单内的内容不会被删除。`,
  })
    .then(async () => {
      const result = await listStore.deleteList(list.id, currentContentType.value)
      if (result) {
        await loadLists()
      }
    })
    .catch(() => {})
}

onMounted(() => {
  loadLists()
})
</script>

<style scoped>
.list-manage {
  min-height: 100vh;
  background: #f5f5f5;
}

.loading-center {
  display: flex;
  justify-content: center;
  padding-top: 100px;
}

.list-group {
  margin-top: 12px;
}

.list-icon {
  margin-right: 8px;
}

.list-counts {
  display: flex;
  gap: 8px;
}

.count-badge {
  display: flex;
  align-items: center;
  gap: 4px;
}

.edit-btn {
  width: 60px;
}

.dialog-content {
  width: 300px;
  padding: 20px;
}

.dialog-content h3 {
  text-align: center;
  margin-bottom: 20px;
}

.dialog-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}
</style>
