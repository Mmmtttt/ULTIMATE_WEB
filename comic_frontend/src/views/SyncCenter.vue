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
      <van-cell title="连接设备" label="输入远程后端地址和配对码" />
      <van-field v-model.trim="connectForm.remoteBaseUrl" label="远程地址" placeholder="http://192.168.1.88:5000" />
      <van-field v-model.trim="connectForm.pairingCode" label="配对码" placeholder="6位配对码" />
      <van-cell title="本机地址" :value="autoRequesterBaseUrl || '自动检测失败'" label="从当前后端自动检测" />
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

import { syncApi } from '@/api'
import { resolveBackendOrigin } from '@/runtime/endpoint'
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
const listStore = useListStore()
const showListScopePopup = ref(false)
const listScopePeer = ref(null)
const loadingListScopeOptions = ref(false)
const listScopePreviewing = ref(false)
const selectedListScopeId = ref('')
const listScopeKeyword = ref('')
const listScopeDirection = ref('push')
const listScopeOptions = ref([])

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
  const backendOrigin = String(resolveBackendOrigin() || '').trim()
  if (backendOrigin) {
    return backendOrigin
  }
  if (typeof window !== 'undefined' && window.location && window.location.origin) {
    return String(window.location.origin || '').trim()
  }
  return ''
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

async function createInvite() {
  creatingInvite.value = true
  try {
    const requesterBaseUrl = resolveAutoRequesterBaseUrl()
    console.log('[SyncCenter] createInvite: requesterBaseUrl =', requesterBaseUrl)
    const res = await syncApi.createPairingInvite({
      ttl_minutes: Number(inviteTtlMinutes.value || 10),
      requester_base_url: requesterBaseUrl
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
      requester_base_url: requesterBaseUrl
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
  margin-top: 12px;
}

.group-actions {
  padding: 10px 16px 16px;
}

.peer-card {
  margin: 10px 12px;
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  padding: 12px;
  background: var(--surface-2);
}

.peer-main {
  margin-bottom: 10px;
}

.peer-progress {
  margin-bottom: 10px;
  padding: 8px;
  border-radius: 8px;
  background: var(--surface-1);
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
  font-weight: 600;
  color: var(--text-primary);
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
  gap: 8px;
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
