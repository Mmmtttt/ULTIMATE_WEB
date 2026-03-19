<template>
  <div class="sync-center-page">
    <van-nav-bar title="Data Sync" left-text="Back" left-arrow @click-left="$router.back()" />

    <van-cell-group inset class="sync-group">
      <van-cell title="Local Pairing Code" label="Generate code on this device, then use it on the other device." />
      <van-field v-model.number="inviteTtlMinutes" type="number" label="TTL (min)" />
      <div class="group-actions">
        <van-button type="primary" block round :loading="creatingInvite" @click="createInvite">
          Generate Pairing Code
        </van-button>
      </div>
      <van-cell v-if="inviteInfo" title="Code" :value="inviteInfo.pairing_code" />
      <van-cell v-if="inviteInfo" title="Expires At" :value="inviteInfo.expires_at" />
    </van-cell-group>

    <van-cell-group inset class="sync-group">
      <van-cell title="Connect Peer" label="Enter remote backend address and pairing code." />
      <van-field v-model.trim="connectForm.remoteBaseUrl" label="Remote URL" placeholder="http://192.168.1.88:5000" />
      <van-field v-model.trim="connectForm.pairingCode" label="Pairing Code" placeholder="6-digit code" />
      <van-field v-model.trim="connectForm.requesterBaseUrl" label="Local URL (optional)" placeholder="http://192.168.1.100:5000" />
      <div class="group-actions">
        <van-button type="primary" block round :loading="connectingPeer" @click="connectPeer">
          Connect
        </van-button>
      </div>
    </van-cell-group>

    <van-cell-group inset class="sync-group">
      <van-cell title="Paired Peers" :value="`Total ${peers.length}`">
        <template #right-icon>
          <van-button size="small" plain type="primary" :loading="loadingPeers" @click.stop="loadPeers">
            Refresh
          </van-button>
        </template>
      </van-cell>

      <template v-if="peers.length > 0">
        <div v-for="peer in peers" :key="peer.peer_id" class="peer-card">
          <div class="peer-main">
            <div class="peer-name">{{ peer.display_name || peer.peer_id }}</div>
            <div class="peer-meta">ID: {{ peer.peer_id }}</div>
            <div class="peer-meta">URL: {{ peer.remote_base_url || '-' }}</div>
            <div class="peer-meta">Last Sync: {{ peer.last_sync_at || '-' }}</div>
          </div>
          <div class="peer-actions">
            <van-button size="small" type="primary" :loading="isPeerActionLoading(peer.peer_id, 'push')" @click="pushToPeer(peer)">
              Push
            </van-button>
            <van-button size="small" type="success" :loading="isPeerActionLoading(peer.peer_id, 'pull')" @click="pullFromPeer(peer)">
              Pull
            </van-button>
            <van-button size="small" type="danger" plain :loading="isPeerActionLoading(peer.peer_id, 'remove')" @click="removePeer(peer)">
              Remove
            </van-button>
          </div>
        </div>
      </template>

      <van-empty v-else description="No paired peers yet" />
    </van-cell-group>

    <van-cell-group inset class="sync-group">
      <van-cell title="Operation Logs" />
      <div class="log-list">
        <div v-if="logs.length === 0" class="log-empty">No logs yet.</div>
        <div v-for="item in logs" :key="item.id" class="log-item">
          <div class="log-time">{{ item.time }}</div>
          <div class="log-text">{{ item.text }}</div>
        </div>
      </div>
    </van-cell-group>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'

import { syncApi } from '@/api'

const inviteTtlMinutes = ref(10)
const creatingInvite = ref(false)
const connectingPeer = ref(false)
const loadingPeers = ref(false)

const inviteInfo = ref(null)
const peers = ref([])
const logs = ref([])
const peerActionLoading = ref({})

const connectForm = reactive({
  remoteBaseUrl: '',
  pairingCode: '',
  requesterBaseUrl: ''
})

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

async function createInvite() {
  creatingInvite.value = true
  try {
    const res = await syncApi.createPairingInvite({
      ttl_minutes: Number(inviteTtlMinutes.value || 10)
    })
    inviteInfo.value = res.data
    appendLog(`Invite generated: code=${res?.data?.pairing_code || '-'}`)
    showSuccessToast('Pairing code created')
  } catch (error) {
    showFailToast(error?.message || 'Create invite failed')
  } finally {
    creatingInvite.value = false
  }
}

async function connectPeer() {
  if (!connectForm.remoteBaseUrl || !connectForm.pairingCode) {
    showFailToast('Remote URL and pairing code are required')
    return
  }
  connectingPeer.value = true
  try {
    const res = await syncApi.connectPairing({
      remote_base_url: connectForm.remoteBaseUrl,
      pairing_code: connectForm.pairingCode,
      requester_base_url: connectForm.requesterBaseUrl
    })
    appendLog(`Connected peer: ${res?.data?.peer_id || '-'}`)
    showSuccessToast('Peer connected')
    connectForm.pairingCode = ''
    await loadPeers()
  } catch (error) {
    showFailToast(error?.message || 'Connect failed')
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
    showFailToast(error?.message || 'Load peers failed')
  } finally {
    loadingPeers.value = false
  }
}

async function pushToPeer(peer) {
  const peerId = peer.peer_id
  setPeerActionLoading(peerId, 'push', true)
  try {
    const res = await syncApi.pushDirectional(peerId)
    appendLog(`Push ${peerId}: ${res?.data?.status || 'completed'}`)
    showSuccessToast('Push done')
    await loadPeers()
  } catch (error) {
    showFailToast(error?.message || 'Push failed')
  } finally {
    setPeerActionLoading(peerId, 'push', false)
  }
}

async function pullFromPeer(peer) {
  const peerId = peer.peer_id
  setPeerActionLoading(peerId, 'pull', true)
  try {
    const res = await syncApi.pullDirectional(peerId)
    appendLog(`Pull ${peerId}: ${res?.data?.status || 'completed'}`)
    showSuccessToast('Pull done')
    await loadPeers()
  } catch (error) {
    showFailToast(error?.message || 'Pull failed')
  } finally {
    setPeerActionLoading(peerId, 'pull', false)
  }
}

async function removePeer(peer) {
  const peerId = peer.peer_id
  try {
    await showConfirmDialog({
      title: 'Remove Peer',
      message: `Remove peer ${peer.display_name || peerId}?`
    })
  } catch {
    return
  }

  setPeerActionLoading(peerId, 'remove', true)
  try {
    await syncApi.removePeer(peerId)
    appendLog(`Peer removed: ${peerId}`)
    showSuccessToast('Peer removed')
    await loadPeers()
  } catch (error) {
    showFailToast(error?.message || 'Remove failed')
  } finally {
    setPeerActionLoading(peerId, 'remove', false)
  }
}

onMounted(async () => {
  await loadPeers()
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
