<template>
  <div class="sync-center-page desktop-page-shell">
    <van-nav-bar title="数据同步" left-text="返回" left-arrow @click-left="$router.back()" />

    <van-cell-group inset class="sync-group">
      <van-cell title="本地配对码" label="在本设备上生成配对码，然后在其他设备上使用" />
      <van-field v-model.number="inviteTtlMinutes" type="number" label="有效期(分钟)" />
      <div class="group-actions">
        <van-button type="primary" block round :loading="creatingInvite" @click="createInvite">
          生成配对码
        </van-button>
      </div>
      <van-cell v-if="inviteInfo" title="配对码" :value="inviteInfo.pairing_code" />
      <van-cell v-if="inviteInfo" title="过期时间" :value="inviteInfo.expires_at" />
    </van-cell-group>

    <van-cell-group inset class="sync-group">
      <van-cell title="连接设备" label="输入远程前端入口地址和配对码" />
      <van-field v-model.trim="connectForm.remoteBaseUrl" label="远程入口" placeholder="https://192.168.1.88:5173" />
      <van-field v-model.trim="connectForm.pairingCode" label="配对码" placeholder="6位配对码" />
      <van-cell title="本机入口" :value="autoRequesterBaseUrl || '自动检测失败'" label="从当前页面地址自动检测" />
      <div class="group-actions">
        <van-button type="primary" block round :loading="connectingPeer" @click="connectPeer">
          连接
        </van-button>
      </div>
    </van-cell-group>

    <van-cell-group inset class="sync-group">
      <van-cell title="已配对设备" :value="`共 ${peers.length} 个`">
        <template #right-icon>
          <van-button size="small" plain type="primary" :loading="loadingPeers" @click.stop="loadPeers">
            刷新
          </van-button>
        </template>
      </van-cell>

      <template v-if="peers.length > 0">
        <div v-for="peer in peers" :key="peer.peer_id" class="peer-card">
          <div class="peer-main">
            <div class="peer-name">{{ peer.display_name || peer.peer_id }}</div>
            <div class="peer-meta">ID: {{ peer.peer_id }}</div>
            <div class="peer-meta">地址: {{ peer.remote_base_url || '-' }}</div>
            <div class="peer-meta">上次同步: {{ peer.last_sync_at || '-' }}</div>
          </div>
          <div v-if="getPeerTask(peer.peer_id)" class="peer-progress">
            <div class="peer-progress-head">
              <span>{{ formatTaskTitle(getPeerTask(peer.peer_id)) }}</span>
              <span>{{ Number(getPeerTask(peer.peer_id)?.progress || 0) }}%</span>
            </div>
            <van-progress
              :percentage="Math.max(0, Math.min(100, Number(getPeerTask(peer.peer_id)?.progress || 0)))"
              :show-pivot="false"
              :stroke-width="6"
            />
            <div class="peer-meta">状态: {{ getPeerTask(peer.peer_id)?.status || '-' }} | 阶段: {{ getPeerTask(peer.peer_id)?.stage || '-' }}</div>
            <div class="peer-meta" v-if="getPeerTask(peer.peer_id)?.message">{{ getPeerTask(peer.peer_id)?.message }}</div>
            <div class="peer-meta" v-if="formatTaskExtra(getPeerTask(peer.peer_id))">{{ formatTaskExtra(getPeerTask(peer.peer_id)) }}</div>
          </div>
          <div class="peer-actions">
            <van-button size="small" plain type="primary" :loading="isPeerActionLoading(peer.peer_id, 'preview_push')" @click="previewAndConfirm(peer, 'push')">
              预览并推送
            </van-button>
            <van-button size="small" plain type="success" :loading="isPeerActionLoading(peer.peer_id, 'preview_pull')" @click="previewAndConfirm(peer, 'pull')">
              预览并拉取
            </van-button>
          </div>
          <div class="peer-actions peer-actions-second">
            <van-button size="small" type="warning" plain :loading="isPeerActionLoading(peer.peer_id, 'list_scope')" @click="openListScopeDialog(peer)">
              按清单推送
            </van-button>
            <van-button size="small" type="primary" plain :loading="isPeerActionLoading(peer.peer_id, 'list_scope_pull')" @click="openListScopeDialog(peer, 'pull')">
              按清单拉取
            </van-button>
            <van-button size="small" type="danger" plain :loading="isPeerActionLoading(peer.peer_id, 'remove')" @click="removePeer(peer)">
              移除
            </van-button>
          </div>
        </div>
      </template>

      <van-empty v-else description="暂无配对设备" />
    </van-cell-group>

    <van-cell-group inset class="sync-group">
      <van-cell title="操作日志" />
      <div class="log-list">
        <div v-if="logs.length === 0" class="log-empty">暂无日志</div>
        <div v-for="item in logs" :key="item.id" class="log-item">
          <div class="log-time">{{ item.time }}</div>
          <div class="log-text">{{ item.text }}</div>
        </div>
      </div>
    </van-cell-group>

    <van-cell-group inset class="sync-group transfer-group">
      <van-cell
        clickable
        title="局域网传输"
        :label="transferExpanded ? '临时传文字或文件，不参与数据同步' : '独立工具，默认收起，点击展开'"
        :value="transferExpanded ? `${transferItems.length} 项` : '点击展开'"
        @click="toggleTransferPanel"
      >
        <template #right-icon>
          <van-icon :name="transferExpanded ? 'arrow-up' : 'arrow-down'" class="transfer-collapse-icon" />
        </template>
      </van-cell>

      <div v-if="transferExpanded" class="transfer-board">
        <div class="transfer-compose">
          <div class="transfer-compose-card text-card">
            <div class="transfer-card-head">
              <span class="transfer-icon">TXT</span>
              <div>
                <div class="transfer-title">发布文字</div>
                <div class="transfer-desc">适合链接、验证码、短笔记，手机打开即可复制。</div>
              </div>
            </div>
            <van-field
              v-model="transferText"
              type="textarea"
              rows="3"
              autosize
              maxlength="4000"
              show-word-limit
              placeholder="输入要在局域网里临时传递的文字"
              class="transfer-textarea"
            />
            <van-field
              v-model.trim="transferTextName"
              placeholder="文件名，可选，例如 note.txt"
              class="transfer-inline-field"
            />
            <van-button type="primary" round block :loading="publishingTransferText" @click="publishTransferText">
              发布文字
            </van-button>
          </div>

          <div class="transfer-compose-card file-card">
            <div class="transfer-card-head">
              <span class="transfer-icon">LAN</span>
              <div>
                <div class="transfer-title">传输文件</div>
                <div class="transfer-desc">终端可上传文件；服务器也可登记本机文件路径供手机下载。</div>
              </div>
            </div>

            <input
              ref="transferFileInput"
              type="file"
              class="transfer-hidden-input"
              @change="handleTransferFileSelected"
            />
            <van-button round block plain type="primary" :loading="uploadingTransferFile" @click="triggerTransferUpload">
              上传当前设备文件
            </van-button>

            <div class="server-file-form">
              <van-field
                v-model.trim="serverFilePath"
                placeholder="服务器文件路径，例如 D:\\share\\movie.zip"
                class="transfer-inline-field"
              />
              <van-field
                v-model.trim="serverFileName"
                placeholder="下载文件名，可选"
                class="transfer-inline-field"
              />
              <van-button type="success" round block :loading="registeringServerFile" @click="registerTransferServerFile">
                登记服务器文件
              </van-button>
            </div>
          </div>
        </div>

        <div class="transfer-list-head">
          <span>当前可取件</span>
          <div class="transfer-list-tools">
            <span>{{ transferItems.length }} 项</span>
            <van-button size="mini" plain type="primary" :loading="loadingTransferItems" @click.stop="loadTransferItems">
              刷新
            </van-button>
          </div>
        </div>
        <div v-if="loadingTransferItems && transferItems.length === 0" class="transfer-loading">
          <van-loading size="20px">加载传输列表...</van-loading>
        </div>
        <van-empty v-else-if="transferItems.length === 0" description="暂无可传输内容" />
        <div v-else class="transfer-list">
          <div v-for="item in transferItems" :key="item.id" class="transfer-item">
            <div class="transfer-item-main">
              <div class="transfer-item-title">
                <span class="kind-pill" :class="item.kind">{{ formatTransferKind(item.kind) }}</span>
                <span>{{ item.name || '未命名内容' }}</span>
              </div>
              <div class="transfer-item-meta">
                {{ formatTransferSize(item.size) }} · {{ item.created_at || '-' }}
              </div>
              <div v-if="item.kind === 'server_file' && item.server_path" class="transfer-item-path">
                {{ item.server_path }}
              </div>
              <div v-if="item.kind === 'text'" class="transfer-text-preview">
                {{ item.text }}
              </div>
            </div>
            <div class="transfer-item-actions">
              <van-button v-if="item.kind === 'text'" size="small" round plain type="primary" @click="copyTransferText(item)">
                复制
              </van-button>
              <van-button size="small" round type="primary" @click="downloadTransferItem(item)">
                下载
              </van-button>
              <van-button size="small" round plain type="danger" @click="deleteTransferItem(item)">
                删除
              </van-button>
            </div>
          </div>
        </div>
      </div>
    </van-cell-group>

    <van-popup
      v-model:show="showListScopePopup"
      round
      :position="isDesktopListScopePopup ? 'center' : 'bottom'"
      :class="['list-scope-popup', { 'list-scope-popup-desktop': isDesktopListScopePopup }]"
      :style="listScopePopupStyle"
    >
      <div class="list-scope-popup-head">
        <div>
          <div class="list-scope-popup-title">{{ listScopeDirection === 'pull' ? '按清单拉取' : '按清单推送' }}</div>
          <div class="list-scope-popup-subtitle">
            {{ listScopeDirection === 'pull'
              ? '从远端选择清单，仅拉取本机缺失的内容，并保留当前清单和标签信息。'
              : '从本机选择清单，仅推送对端缺失的内容，并保留当前清单和标签信息。' }}
          </div>
          <div v-if="listScopePeer" class="list-scope-popup-peer">
            {{ listScopeDirection === 'pull' ? '来源设备' : '目标设备' }}：{{ listScopePeer.display_name || listScopePeer.peer_id }}
          </div>
        </div>
      </div>

      <van-search
        v-model.trim="listScopeKeyword"
        :placeholder="listScopeDirection === 'pull' ? '搜索远端清单名称' : '搜索本机清单名称'"
        shape="round"
        class="list-scope-search"
      />

      <div class="list-scope-popup-body">
        <van-loading v-if="loadingListScopeOptions" size="22px" class="list-scope-loading" />
        <template v-else>
          <van-radio-group v-if="filteredListScopeOptions.length > 0" v-model="selectedListScopeId">
            <van-cell
              v-for="item in filteredListScopeOptions"
              :key="item.id"
              clickable
              class="list-scope-cell"
              @click="selectedListScopeId = item.id"
            >
              <template #title>
                <div class="list-scope-cell-title">{{ item.name }}</div>
                <div class="list-scope-cell-meta">
                  漫画 {{ Number(item.comic_count || 0) }} · 视频 {{ Number(item.video_count || 0) }}
                </div>
                <div v-if="item.desc" class="list-scope-cell-desc">{{ item.desc }}</div>
              </template>
              <template #right-icon>
                <van-radio :name="item.id" />
              </template>
            </van-cell>
          </van-radio-group>
          <van-empty v-else :description="listScopeDirection === 'pull' ? '远端暂无可拉取清单' : '暂无可推送清单'" />
        </template>
      </div>

      <div class="list-scope-popup-actions">
        <van-button round plain block @click="closeListScopeDialog">
          取消
        </van-button>
        <van-button
          round
          type="primary"
          block
          :disabled="!selectedListScopeId"
          :loading="listScopePreviewing"
          @click="previewSelectedListScope"
        >
          {{ listScopeDirection === 'pull' ? '预览并拉取' : '预览并推送' }}
        </van-button>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'

import { syncApi, transferApi } from '@/api'
import { resolveBackendOrigin } from '@/runtime/endpoint'
import { useAuthStore } from '@/stores/auth'
import { useListStore } from '@/stores/list'

const inviteTtlMinutes = ref(10)
const creatingInvite = ref(false)
const connectingPeer = ref(false)
const loadingPeers = ref(false)

const inviteInfo = ref(null)
const peers = ref([])
const logs = ref([])
const peerActionLoading = ref({})
const peerTaskMap = ref({})
const taskPollingTokens = ref({})
const pageAlive = ref(true)
const isDesktopListScopePopup = ref(false)
const authStore = useAuthStore()
const listStore = useListStore()
const showListScopePopup = ref(false)
const listScopePeer = ref(null)
const loadingListScopeOptions = ref(false)
const listScopePreviewing = ref(false)
const selectedListScopeId = ref('')
const listScopeKeyword = ref('')
const listScopeDirection = ref('push')
const listScopeOptions = ref([])
const transferExpanded = ref(false)
const transferItems = ref([])
const loadingTransferItems = ref(false)
const publishingTransferText = ref(false)
const uploadingTransferFile = ref(false)
const registeringServerFile = ref(false)
const transferText = ref('')
const transferTextName = ref('')
const serverFilePath = ref('')
const serverFileName = ref('')
const transferFileInput = ref(null)

const connectForm = reactive({
  remoteBaseUrl: '',
  pairingCode: ''
})

const autoRequesterBaseUrl = ref('')

const listScopePopupStyle = computed(() => {
  if (!isDesktopListScopePopup.value) {
    return {}
  }
  return {
    width: 'min(680px, calc(100vw - 32px))',
    maxHeight: 'min(82vh, 760px)'
  }
})

const filteredListScopeOptions = computed(() => {
  const keyword = String(listScopeKeyword.value || '').trim().toLowerCase()
  const items = Array.isArray(listScopeOptions.value) ? listScopeOptions.value : []
  const filtered = items.filter((item) => {
    const total = Number(item?.comic_count || 0) + Number(item?.video_count || 0)
    if (total <= 0) {
      return false
    }
    if (!keyword) {
      return true
    }
    return String(item?.name || '').toLowerCase().includes(keyword)
      || String(item?.desc || '').toLowerCase().includes(keyword)
  })
  return filtered.sort((a, b) => {
    const aTotal = Number(a?.comic_count || 0) + Number(a?.video_count || 0)
    const bTotal = Number(b?.comic_count || 0) + Number(b?.video_count || 0)
    return bTotal - aTotal
  })
})

function resolveAutoRequesterBaseUrl() {
  if (typeof window !== 'undefined' && window.location && window.location.origin) {
    return String(window.location.origin || '').trim()
  }
  const backendOrigin = String(resolveBackendOrigin() || '').trim()
  if (backendOrigin) {
    return backendOrigin
  }
  return ''
}

function currentSyncSpaceMode() {
  return authStore.mode === 'normal' ? 'normal' : 'private'
}

function updateListScopePopupLayout() {
  if (typeof window === 'undefined') {
    isDesktopListScopePopup.value = false
    return
  }
  isDesktopListScopePopup.value = window.innerWidth >= 768
}

function appendLog(text) {
  logs.value.unshift({
    id: `${Date.now()}_${Math.random()}`,
    time: new Date().toLocaleString(),
    text: String(text || '')
  })
  if (logs.value.length > 40) {
    logs.value = logs.value.slice(0, 40)
  }
}

function setPeerActionLoading(peerId, action, value) {
  peerActionLoading.value = {
    ...peerActionLoading.value,
    [`${peerId}_${action}`]: Boolean(value)
  }
}

function isPeerActionLoading(peerId, action) {
  return Boolean(peerActionLoading.value[`${peerId}_${action}`])
}

function setPeerTask(peerId, task) {
  peerTaskMap.value = {
    ...peerTaskMap.value,
    [peerId]: task || null
  }
}

function getPeerTask(peerId) {
  return peerTaskMap.value[peerId] || null
}

function formatTaskTitle(task) {
  const taskKind = String(task?.task_kind || '').trim().toLowerCase()
  if (taskKind === 'list_scope_push') {
    return '清单推送任务'
  }
  if (taskKind === 'list_scope_pull') {
    return '清单拉取任务'
  }
  const direction = String(task?.direction || '').toUpperCase()
  if (!direction) {
    return '同步任务'
  }
  return `${direction} 任务`
}

function formatTaskExtra(task) {
  const extra = task?.extra || {}
  if (!extra || typeof extra !== 'object') {
    return ''
  }
  const parts = []
  if (Number(extra.record_count || 0) > 0) {
    parts.push(`records=${Number(extra.record_count || 0)}`)
  }
  if (extra.list_name) {
    parts.unshift(`list=${extra.list_name}`)
  }
  if (Number(extra.pending_content_count || 0) > 0) {
    parts.push(`contents=${Number(extra.pending_content_count || 0)}`)
  }
  if (Number(extra.file_count || 0) > 0) {
    parts.push(`files=${Number(extra.file_count || 0)}`)
  }
  if (Number(extra.applied_files || 0) > 0) {
    parts.push(`applied=${Number(extra.applied_files || 0)}`)
  }
  if (Number(extra.downloaded_bytes || 0) > 0) {
    parts.push(`downloaded=${Math.round(Number(extra.downloaded_bytes || 0) / 1024 / 1024)}MB`)
  }
  return parts.join(', ')
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function formatTransferKind(kind) {
  const value = String(kind || '').trim()
  if (value === 'text') return '文字'
  if (value === 'server_file') return '服务器'
  if (value === 'upload') return '上传'
  return '文件'
}

function formatTransferSize(size) {
  const bytes = Number(size || 0)
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return '0 B'
  }
  if (bytes < 1024) {
    return `${bytes} B`
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  if (bytes < 1024 * 1024 * 1024) {
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  }
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}

async function loadTransferItems() {
  loadingTransferItems.value = true
  try {
    const res = await transferApi.listItems()
    transferItems.value = Array.isArray(res?.data?.items) ? res.data.items : []
  } catch (error) {
    showFailToast(error?.message || '加载传输列表失败')
  } finally {
    loadingTransferItems.value = false
  }
}

async function toggleTransferPanel() {
  transferExpanded.value = !transferExpanded.value
  if (transferExpanded.value && transferItems.value.length === 0) {
    await loadTransferItems()
  }
}

async function publishTransferText() {
  if (!String(transferText.value || '').trim()) {
    showFailToast('请输入要发布的文字')
    return
  }
  publishingTransferText.value = true
  try {
    const res = await transferApi.publishText(transferText.value, transferTextName.value)
    appendLog(`局域网传输: 已发布文字 ${res?.data?.name || ''}`)
    transferText.value = ''
    transferTextName.value = ''
    showSuccessToast('文字已发布')
    await loadTransferItems()
  } catch (error) {
    showFailToast(error?.message || '发布文字失败')
  } finally {
    publishingTransferText.value = false
  }
}

function triggerTransferUpload() {
  transferFileInput.value?.click?.()
}

async function handleTransferFileSelected(event) {
  const file = event?.target?.files?.[0]
  if (!file) {
    return
  }
  uploadingTransferFile.value = true
  try {
    const res = await transferApi.uploadFile(file)
    appendLog(`局域网传输: 已上传文件 ${res?.data?.name || file.name}`)
    showSuccessToast('文件已上传')
    await loadTransferItems()
  } catch (error) {
    showFailToast(error?.message || '上传文件失败')
  } finally {
    uploadingTransferFile.value = false
    if (event?.target) {
      event.target.value = ''
    }
  }
}

async function registerTransferServerFile() {
  if (!String(serverFilePath.value || '').trim()) {
    showFailToast('请输入服务器文件路径')
    return
  }
  registeringServerFile.value = true
  try {
    const res = await transferApi.registerServerFile(serverFilePath.value, serverFileName.value)
    appendLog(`局域网传输: 已登记服务器文件 ${res?.data?.name || serverFilePath.value}`)
    serverFilePath.value = ''
    serverFileName.value = ''
    showSuccessToast('服务器文件已登记')
    await loadTransferItems()
  } catch (error) {
    showFailToast(error?.message || '登记服务器文件失败')
  } finally {
    registeringServerFile.value = false
  }
}

function downloadTransferItem(item) {
  if (!item?.id) return
  const url = transferApi.getDownloadUrl(item.id, authStore.mode)
  window.open(url, '_blank')
}

async function copyTransferText(item) {
  const text = String(item?.text || '')
  if (!text) {
    showFailToast('没有可复制的文字')
    return
  }
  try {
    await navigator.clipboard.writeText(text)
    showSuccessToast('已复制')
  } catch (error) {
    console.warn('复制失败:', error)
    showFailToast('复制失败，请手动选择文字')
  }
}

async function deleteTransferItem(item) {
  if (!item?.id) return
  try {
    await showConfirmDialog({
      title: '删除传输项',
      message: item.kind === 'server_file'
        ? '只删除传输入口，不会删除服务器原文件。'
        : `确定删除 ${item.name || '该传输项'} 吗？`
    })
  } catch {
    return
  }
  try {
    await transferApi.deleteItem(item.id)
    appendLog(`局域网传输: 已删除 ${item.name || item.id}`)
    showSuccessToast('已删除')
    await loadTransferItems()
  } catch (error) {
    showFailToast(error?.message || '删除失败')
  }
}

async function createInvite() {
  creatingInvite.value = true
  try {
    const requesterBaseUrl = resolveAutoRequesterBaseUrl()
    console.log('[SyncCenter] createInvite: requesterBaseUrl =', requesterBaseUrl)
    const res = await syncApi.createPairingInvite({
      ttl_minutes: Number(inviteTtlMinutes.value || 10),
      requester_base_url: requesterBaseUrl,
      requester_space_mode: currentSyncSpaceMode()
    })
    inviteInfo.value = res.data
    console.log('[SyncCenter] createInvite success:', res.data)
    appendLog(`已生成配对码: code=${res?.data?.pairing_code || '-'}`)
    showSuccessToast('配对码已生成')
  } catch (error) {
    console.error('[SyncCenter] createInvite failed:', error)
    showFailToast(error?.message || '生成配对码失败')
  } finally {
    creatingInvite.value = false
  }
}

async function connectPeer() {
  if (!connectForm.remoteBaseUrl || !connectForm.pairingCode) {
    showFailToast('请填写远程地址和配对码')
    return
  }

  const requesterBaseUrl = resolveAutoRequesterBaseUrl()
  autoRequesterBaseUrl.value = requesterBaseUrl
  console.log(
    '[SyncCenter] connectPeer: remoteBaseUrl =', connectForm.remoteBaseUrl,
    'pairingCode =', connectForm.pairingCode,
    'requesterBaseUrl =', requesterBaseUrl
  )
  if (!requesterBaseUrl) {
    showFailToast('无法自动检测本机地址')
    return
  }

  connectingPeer.value = true
  try {
    const res = await syncApi.connectPairing({
      remote_base_url: connectForm.remoteBaseUrl,
      pairing_code: connectForm.pairingCode,
      requester_base_url: requesterBaseUrl,
      remote_space_mode: currentSyncSpaceMode(),
      requester_space_mode: currentSyncSpaceMode()
    })
    console.log('[SyncCenter] connectPeer success:', res.data)
    appendLog(`已连接设备: ${res?.data?.peer_id || '-'}, 本机=${requesterBaseUrl}`)
    showSuccessToast('设备已连接')
    connectForm.pairingCode = ''
    await loadPeers()
  } catch (error) {
    console.error('[SyncCenter] connectPeer failed:', error)
    appendLog(`连接失败: ${error?.message || error || 'unknown error'}`)
    showFailToast(error?.message || '连接失败')
  } finally {
    connectingPeer.value = false
  }
}

async function loadPeers() {
  loadingPeers.value = true
  try {
    const res = await syncApi.listPeers()
    peers.value = Array.isArray(res.data) ? res.data : []
  } catch (error) {
    showFailToast(error?.message || '加载设备列表失败')
  } finally {
    loadingPeers.value = false
  }
}

function formatEstimateMessage(peer, direction, estimate) {
  const dataSync = estimate?.data_sync || {}
  const assetSync = estimate?.asset_sync || {}
  const totalRecords = Number(dataSync?.total_records || 0)
  const datasetCounts = dataSync?.dataset_counts || {}
  const datasetLines = Object.keys(datasetCounts)
    .filter((key) => Number(datasetCounts[key] || 0) > 0)
    .map((key) => `${key}: ${datasetCounts[key]}`)

  const assetStatus = assetSync?.status || 'unknown'
  const fileCount = Number(assetSync?.file_count || 0)
  const totalMb = Number(assetSync?.total_mb || 0)
  const assetLine = `资源: 状态=${assetStatus}, 文件数=${fileCount}, 大小=${totalMb} MB`
  const msg = assetSync?.message ? `\n资源消息: ${assetSync.message}` : ''
  const lines = [
    `设备: ${peer.display_name || peer.peer_id}`,
    `方向: ${direction}`,
    `数据记录: ${totalRecords}`,
    datasetLines.length > 0 ? `数据详情: ${datasetLines.join(', ')}` : '数据详情: 无变化',
    assetLine + msg
  ]
  return lines.join('\n')
}

function formatListScopeEstimateMessage(peer, estimate, direction = 'push') {
  const scope = estimate?.list_scope || {}
  const dataSync = estimate?.data_sync || {}
  const assetSync = estimate?.asset_sync || {}
  const datasetCounts = dataSync?.dataset_counts || {}
  const datasetLines = Object.keys(datasetCounts)
    .filter((key) => Number(datasetCounts[key] || 0) > 0)
    .map((key) => `${key}: ${datasetCounts[key]}`)
  const assetStatus = assetSync?.status || 'unknown'
  const fileCount = Number(assetSync?.file_count || 0)
  const totalMb = Number(assetSync?.total_mb || 0)
  const actionLabel = direction === 'pull' ? '拉取' : '推送'
  const existingLabel = direction === 'pull' ? '本机已存在' : '对端已存在'

  return [
    `设备: ${peer.display_name || peer.peer_id}`,
    `清单: ${scope?.list_name || scope?.list_id || '-'}`,
    `原始内容数: ${Number(scope?.source_content_count || 0)}`,
    `待${actionLabel}内容数: ${Number(scope?.pending_content_count || 0)}`,
    `${existingLabel}: ${Number(scope?.skipped_existing_content_count || 0)}`,
    datasetLines.length > 0 ? `数据详情: ${datasetLines.join(', ')}` : '数据详情: 无变化',
    `资源: 状态=${assetStatus}, 文件数=${fileCount}, 大小=${totalMb} MB`,
  ].join('\n')
}

async function previewAndConfirm(peer, direction) {
  const peerId = peer.peer_id
  const loadingKey = direction === 'push' ? 'preview_push' : 'preview_pull'
  setPeerActionLoading(peerId, loadingKey, true)
  try {
    const res = await syncApi.previewDirectional(peerId, direction)
    const estimate = res?.data || {}
    const actionLabel = direction === 'pull' ? '拉取' : '推送'
    appendLog(`预览并${actionLabel} ${peerId}: 数据=${estimate?.data_sync?.total_records || 0}, 资源=${estimate?.asset_sync?.file_count || 0}`)

    await showConfirmDialog({
      title: `预览并${actionLabel}`,
      message: formatEstimateMessage(peer, direction, estimate),
      confirmButtonText: `确认${actionLabel}`,
      cancelButtonText: '取消'
    })

    if (direction === 'push') {
      await pushToPeer(peer)
    } else {
      await pullFromPeer(peer)
    }
  } catch (error) {
    const msg = String(error?.message || '')
    if (msg && !msg.includes('cancel')) {
      showFailToast(msg || '预览失败')
    }
  } finally {
    setPeerActionLoading(peerId, loadingKey, false)
  }
}

async function openListScopeDialog(peer, direction = 'push') {
  const peerId = String(peer?.peer_id || '').trim()
  if (!peerId) {
    showFailToast('无效的设备')
    return
  }
  const directionKey = direction === 'pull' ? 'pull' : 'push'
  const loadingKey = directionKey === 'pull' ? 'list_scope_pull' : 'list_scope'
  setPeerActionLoading(peerId, loadingKey, true)
  loadingListScopeOptions.value = true
  try {
    listScopeDirection.value = directionKey
    if (directionKey === 'pull') {
      const res = await syncApi.getListScopeOptions(peerId)
      listScopeOptions.value = Array.isArray(res?.data) ? res.data : []
    } else {
      await listStore.fetchLists()
      listScopeOptions.value = Array.isArray(listStore.lists) ? listStore.lists : []
    }
    listScopePeer.value = peer
    listScopeKeyword.value = ''
    const firstOption = filteredListScopeOptions.value[0]
    selectedListScopeId.value = firstOption?.id || ''
    showListScopePopup.value = true
  } catch (error) {
    showFailToast(error?.message || '加载清单失败')
  } finally {
    loadingListScopeOptions.value = false
    setPeerActionLoading(peerId, loadingKey, false)
  }
}

function closeListScopeDialog() {
  showListScopePopup.value = false
  listScopePeer.value = null
  selectedListScopeId.value = ''
  listScopeKeyword.value = ''
  listScopeDirection.value = 'push'
  listScopeOptions.value = []
}

async function previewSelectedListScope() {
  const peer = listScopePeer.value
  const peerId = String(peer?.peer_id || '').trim()
  const listId = String(selectedListScopeId.value || '').trim()
  const direction = listScopeDirection.value === 'pull' ? 'pull' : 'push'
  const actionLabel = direction === 'pull' ? '拉取' : '推送'
  if (!peerId || !listId) {
    showFailToast(`请选择${direction === 'pull' ? '来源设备和远端清单' : '目标设备和清单'}`)
    return
  }

  listScopePreviewing.value = true
  try {
    const res = await syncApi.previewListScopeWithDirection(peerId, listId, direction)
    const estimate = res?.data || {}
    const scope = estimate?.list_scope || {}
    const totalRecords = Number(estimate?.data_sync?.total_records || 0)
    const assetFiles = Number(estimate?.asset_sync?.file_count || 0)
    const sourceCount = Number(scope?.source_content_count || 0)
    const pendingCount = Number(scope?.pending_content_count || 0)
    const skippedCount = Number(scope?.skipped_existing_content_count || 0)
    const existingLabel = direction === 'pull' ? '本机已存在' : '对端已存在'
    appendLog(
      `预览清单${actionLabel} ${peerId}: 清单=${scope?.list_name || listId}, 原始=${sourceCount}, 待${actionLabel}=${pendingCount}, ${existingLabel}=${skippedCount}, 数据=${totalRecords}, 资源=${assetFiles}`
    )

    if (totalRecords <= 0 && assetFiles <= 0) {
      showSuccessToast(`该清单暂无需要${actionLabel}的新内容`)
      return
    }

    await showConfirmDialog({
      title: `预览清单${actionLabel}`,
      message: formatListScopeEstimateMessage(peer, estimate, direction),
      confirmButtonText: `确认${actionLabel}`,
      cancelButtonText: '取消'
    })

    showListScopePopup.value = false
    await runListScopeTask(peer, listId, direction, String(scope?.list_name || '').trim())
  } catch (error) {
    const msg = String(error?.message || '')
    if (msg && !msg.includes('cancel')) {
      showFailToast(msg || '预览失败')
    }
  } finally {
    listScopePreviewing.value = false
  }
}

async function runDirectionalTask(peer, direction) {
  const peerId = peer.peer_id
  const actionKey = direction === 'push' ? 'push' : 'pull'
  if (!peerId) {
    showFailToast('无效的设备')
    return
  }
  if (isPeerActionLoading(peerId, actionKey)) {
    return
  }

  const tokenKey = `${peerId}_${actionKey}`
  const token = `${Date.now()}_${Math.random()}`
  taskPollingTokens.value = {
    ...taskPollingTokens.value,
    [tokenKey]: token
  }

  setPeerActionLoading(peerId, actionKey, true)
  try {
    const startRes = await syncApi.startDirectionalTask(peerId, direction)
    const task = startRes?.data || {}
    const taskId = String(task?.task_id || '').trim()
    if (!taskId) {
      throw new Error('任务启动失败：缺少任务ID')
    }

    setPeerTask(peerId, task)
    appendLog(`任务已启动: ${direction} 设备=${peerId}, 任务=${taskId}`)

    while (pageAlive.value) {
      if (taskPollingTokens.value[tokenKey] !== token) {
        break
      }
      await sleep(900)
      const taskRes = await syncApi.getDirectionalTask(taskId)
      const latestTask = taskRes?.data || {}
      setPeerTask(peerId, latestTask)
      const status = String(latestTask?.status || '').toLowerCase()

      if (status === 'completed') {
        const result = latestTask?.result || {}
        const assetCount = Number(result?.asset_sync?.file_count || 0)
        const assetStatus = result?.asset_sync?.status || 'unknown'
        appendLog(`${direction.toUpperCase()} ${peerId}: 已完成, 资源状态=${assetStatus}, 资源数=${assetCount}`)
        showSuccessToast(`${direction.toUpperCase()} 完成`)
        await loadPeers()
        break
      }
      if (status === 'failed') {
        const failedMsg = latestTask?.error?.message || latestTask?.message || `${direction} 失败`
        appendLog(`${direction.toUpperCase()} ${peerId}: 失败, 消息=${failedMsg}`)
        showFailToast(failedMsg)
        break
      }
    }
  } catch (error) {
    showFailToast(error?.message || `${direction} 失败`)
  } finally {
    const current = { ...taskPollingTokens.value }
    delete current[tokenKey]
    taskPollingTokens.value = current
    setPeerActionLoading(peerId, actionKey, false)
  }
}

async function runListScopeTask(peer, listId, direction = 'push', listName = '') {
  const peerId = String(peer?.peer_id || '').trim()
  const directionKey = direction === 'pull' ? 'pull' : 'push'
  const actionLabel = directionKey === 'pull' ? '拉取' : '推送'
  if (!peerId || !listId) {
    showFailToast('缺少同步参数')
    return
  }
  const loadingKey = directionKey === 'pull' ? 'list_scope_pull' : 'list_scope'
  if (isPeerActionLoading(peerId, loadingKey)) {
    return
  }

  const tokenKey = `${peerId}_list_scope_${directionKey}`
  const token = `${Date.now()}_${Math.random()}`
  taskPollingTokens.value = {
    ...taskPollingTokens.value,
    [tokenKey]: token
  }

  setPeerActionLoading(peerId, loadingKey, true)
  try {
    const startRes = await syncApi.startListScopeTask(peerId, listId, directionKey)
    const task = startRes?.data || {}
    const taskId = String(task?.task_id || '').trim()
    if (!taskId) {
      throw new Error('任务启动失败：缺少任务ID')
    }

    setPeerTask(peerId, task)
    appendLog(`清单${actionLabel}任务已启动: 设备=${peerId}, 清单=${listName || listId}, 任务=${taskId}`)

    while (pageAlive.value) {
      if (taskPollingTokens.value[tokenKey] !== token) {
        break
      }
      await sleep(900)
      const taskRes = await syncApi.getListScopeTask(taskId)
      const latestTask = taskRes?.data || {}
      setPeerTask(peerId, latestTask)
      const status = String(latestTask?.status || '').toLowerCase()

      if (status === 'completed') {
        const result = latestTask?.result || {}
        const assetCount = Number(result?.asset_sync?.file_count || 0)
        const resultStatus = String(result?.status || '').trim().toLowerCase()
        appendLog(`清单${actionLabel} ${peerId}: 已完成, 清单=${result?.list_scope?.list_name || listName || listId}, 资源数=${assetCount}`)
        showSuccessToast(resultStatus === 'no_change' ? `清单${actionLabel}无变化` : `清单${actionLabel}完成`)
        await loadPeers()
        break
      }
      if (status === 'failed') {
        const failedMsg = latestTask?.error?.message || latestTask?.message || `清单${actionLabel}失败`
        appendLog(`清单${actionLabel} ${peerId}: 失败, 消息=${failedMsg}`)
        showFailToast(failedMsg)
        break
      }
    }
  } catch (error) {
    showFailToast(error?.message || `清单${actionLabel}失败`)
  } finally {
    const current = { ...taskPollingTokens.value }
    delete current[tokenKey]
    taskPollingTokens.value = current
    setPeerActionLoading(peerId, loadingKey, false)
  }
}

async function pushToPeer(peer) {
  await runDirectionalTask(peer, 'push')
}

async function pullFromPeer(peer) {
  await runDirectionalTask(peer, 'pull')
}

async function removePeer(peer) {
  const peerId = peer.peer_id
  try {
    await showConfirmDialog({
      title: '移除设备',
      message: `确定要移除设备 ${peer.display_name || peerId} 吗？`
    })
  } catch {
    return
  }

  setPeerActionLoading(peerId, 'remove', true)
  try {
    await syncApi.removePeer(peerId)
    appendLog(`设备已移除: ${peerId}`)
    showSuccessToast('设备已移除')
    await loadPeers()
  } catch (error) {
    showFailToast(error?.message || '移除失败')
  } finally {
    setPeerActionLoading(peerId, 'remove', false)
  }
}

onMounted(async () => {
  pageAlive.value = true
  autoRequesterBaseUrl.value = resolveAutoRequesterBaseUrl()
  updateListScopePopupLayout()
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', updateListScopePopupLayout)
  }
  await loadPeers()
})

onUnmounted(() => {
  pageAlive.value = false
  taskPollingTokens.value = {}
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', updateListScopePopupLayout)
  }
})
</script>

<style scoped>
.sync-center-page {
  min-height: 95vh;
  background: transparent;
  padding-bottom: 24px;
}

.sync-group {
  margin: 12px;
  overflow: hidden;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.sync-group :deep(.van-cell),
.sync-group :deep(.van-field) {
  background: transparent;
}

.group-actions {
  padding: 10px 16px 16px;
}

.transfer-group {
  position: relative;
}

.transfer-collapse-icon {
  margin-left: 8px;
  color: var(--text-tertiary);
  font-size: 16px;
  transition: transform 0.18s ease;
}

.transfer-board {
  padding: 12px;
  border-top: 1px solid var(--border-soft);
}

.transfer-compose {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
}

.transfer-compose-card {
  padding: 14px;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  background:
    radial-gradient(circle at 12% 0%, rgba(80, 134, 255, 0.14), transparent 34%),
    var(--surface-1);
  box-shadow: var(--shadow-xs);
}

.transfer-compose-card.file-card {
  background:
    radial-gradient(circle at 90% 0%, rgba(24, 184, 122, 0.14), transparent 34%),
    var(--surface-1);
}

.transfer-card-head {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 12px;
}

.transfer-icon {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 42px;
  height: 30px;
  padding: 0 9px;
  border-radius: 999px;
  color: #fff;
  background: linear-gradient(135deg, var(--brand-600), #76a7ff);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  box-shadow: 0 8px 18px rgba(80, 134, 255, 0.24);
}

.file-card .transfer-icon {
  background: linear-gradient(135deg, #16a36f, #7bdc9b);
  box-shadow: 0 8px 18px rgba(22, 163, 111, 0.22);
}

.transfer-title {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 800;
}

.transfer-desc {
  margin-top: 3px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.transfer-textarea,
.transfer-inline-field {
  margin-bottom: 10px;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  background: var(--surface-2);
  overflow: hidden;
}

.transfer-textarea :deep(.van-field__control) {
  line-height: 1.55;
}

.server-file-form {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--border-soft);
}

.transfer-hidden-input {
  display: none;
}

.transfer-list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 16px 2px 8px;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.transfer-list-tools {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text-tertiary);
  font-size: 12px;
  font-weight: 600;
}

.transfer-loading {
  display: flex;
  justify-content: center;
  padding: 28px 0;
}

.transfer-list {
  display: grid;
  gap: 10px;
}

.transfer-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--border-soft);
  border-radius: 16px;
  background: var(--surface-1);
}

.transfer-item-main {
  min-width: 0;
  flex: 1 1 auto;
}

.transfer-item-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 800;
  word-break: break-word;
}

.kind-pill {
  flex: 0 0 auto;
  padding: 2px 8px;
  border-radius: 999px;
  color: var(--brand-700);
  background: rgba(80, 134, 255, 0.12);
  font-size: 11px;
}

.kind-pill.server_file {
  color: #128058;
  background: rgba(22, 163, 111, 0.13);
}

.kind-pill.upload {
  color: #a15c00;
  background: rgba(245, 158, 11, 0.15);
}

.transfer-item-meta,
.transfer-item-path {
  margin-top: 5px;
  color: var(--text-tertiary);
  font-size: 12px;
  word-break: break-all;
}

.transfer-text-preview {
  margin-top: 8px;
  max-height: 72px;
  overflow: hidden;
  padding: 8px 10px;
  border-radius: 12px;
  color: var(--text-secondary);
  background: var(--surface-2);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.transfer-item-actions {
  flex: 0 0 auto;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.peer-card {
  margin: 12px;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  padding: 14px;
  background: var(--surface-1);
  box-shadow: var(--shadow-xs);
}

.peer-main {
  margin-bottom: 10px;
}

.peer-progress {
  margin-bottom: 10px;
  padding: 10px;
  border-radius: 14px;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
}

.peer-progress-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.peer-name {
  font-size: 15px;
  font-weight: 800;
  color: var(--text-strong);
}

.peer-meta {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  word-break: break-all;
}

.peer-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.peer-actions .van-button {
  flex: 1 1 120px;
  min-width: 112px;
}

.peer-actions-second {
  margin-top: 8px;
}

.log-list {
  padding: 10px 12px 14px;
}

.log-empty {
  color: var(--text-tertiary);
  font-size: 13px;
}

.log-item {
  padding: 8px 0;
  border-bottom: 1px dashed var(--border-soft);
}

.log-time {
  font-size: 11px;
  color: var(--text-tertiary);
}

.log-text {
  font-size: 13px;
  color: var(--text-primary);
  margin-top: 3px;
  word-break: break-word;
}

.list-scope-popup {
  display: flex;
  flex-direction: column;
  padding: 18px 16px calc(18px + env(safe-area-inset-bottom, 0px));
  max-height: min(78vh, 720px);
  overflow: hidden;
  box-sizing: border-box;
}

.list-scope-popup-desktop {
  padding: 20px 20px 18px;
  border-radius: 24px;
  box-shadow: 0 22px 64px rgba(5, 10, 24, 0.32);
}

.list-scope-popup-head {
  margin-bottom: 12px;
}

.list-scope-popup-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.list-scope-popup-subtitle,
.list-scope-popup-peer {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.list-scope-search {
  margin-bottom: 10px;
  padding: 0;
}

.list-scope-popup-body {
  flex: 1 1 auto;
  min-height: 0;
  max-height: min(48vh, 420px);
  overflow-y: auto;
  padding-right: 2px;
}

.list-scope-loading {
  display: flex;
  justify-content: center;
  padding: 28px 0;
}

.list-scope-cell {
  border-radius: 12px;
  margin-bottom: 8px;
  background: var(--surface-1);
}

.list-scope-cell-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.list-scope-cell-meta,
.list-scope-cell-desc {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.list-scope-popup-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
  flex-shrink: 0;
}

@media (max-width: 640px) {
  .sync-group {
    margin-inline: 10px;
    border-radius: 16px;
  }

  .peer-card {
    margin-inline: 10px;
    padding: 12px;
  }

  .transfer-board {
    padding: 10px;
  }

  .transfer-compose {
    grid-template-columns: 1fr;
  }

  .transfer-item {
    flex-direction: column;
  }

  .transfer-item-actions {
    width: 100%;
    justify-content: stretch;
  }

  .transfer-item-actions .van-button {
    flex: 1 1 0;
  }

  .peer-actions .van-button {
    flex: 1 1 calc(50% - 4px);
  }

  .list-scope-popup-actions {
    grid-template-columns: 1fr;
  }
}

@media (min-width: 768px) {
  .list-scope-popup {
    max-height: min(82vh, 760px);
  }

  .list-scope-popup-body {
    max-height: none;
  }
}
</style>
