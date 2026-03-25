<template>
  <div class="sync-center-page">
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
              预览推送
            </van-button>
            <van-button size="small" plain type="success" :loading="isPeerActionLoading(peer.peer_id, 'preview_pull')" @click="previewAndConfirm(peer, 'pull')">
              预览拉取
            </van-button>
          </div>
          <div class="peer-actions peer-actions-second">
            <van-button size="small" type="primary" :loading="isPeerActionLoading(peer.peer_id, 'push')" @click="pushToPeer(peer)">
              推送
            </van-button>
            <van-button size="small" type="success" :loading="isPeerActionLoading(peer.peer_id, 'pull')" @click="pullFromPeer(peer)">
              拉取
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
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'

import { syncApi } from '@/api'
import { resolveBackendOrigin } from '@/runtime/endpoint'

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

const connectForm = reactive({
  remoteBaseUrl: '',
  pairingCode: ''
})

const autoRequesterBaseUrl = ref('')

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
    const res = await syncApi.createPairingInvite({
      ttl_minutes: Number(inviteTtlMinutes.value || 10)
    })
    inviteInfo.value = res.data
    appendLog(`已生成配对码: code=${res?.data?.pairing_code || '-'}`)
    showSuccessToast('配对码已生成')
  } catch (error) {
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
    appendLog(`已连接设备: ${res?.data?.peer_id || '-'}, 本机=${requesterBaseUrl}`)
    showSuccessToast('设备已连接')
    connectForm.pairingCode = ''
    await loadPeers()
  } catch (error) {
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

async function previewAndConfirm(peer, direction) {
  const peerId = peer.peer_id
  const loadingKey = direction === 'push' ? 'preview_push' : 'preview_pull'
  setPeerActionLoading(peerId, loadingKey, true)
  try {
    const res = await syncApi.previewDirectional(peerId, direction)
    const estimate = res?.data || {}
    appendLog(`预览 ${direction} ${peerId}: 数据=${estimate?.data_sync?.total_records || 0}, 资源=${estimate?.asset_sync?.file_count || 0}`)

    await showConfirmDialog({
      title: `预览 ${direction.toUpperCase()}`,
      message: formatEstimateMessage(peer, direction, estimate),
      confirmButtonText: '确认同步',
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
  await loadPeers()
})

onUnmounted(() => {
  pageAlive.value = false
  taskPollingTokens.value = {}
})
</script>

<style scoped>
.sync-center-page {
  min-height: 100vh;
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
</style>
