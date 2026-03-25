<template>
  <div class="comic-local-import-page">
    <van-nav-bar
      title="本地漫画导入"
      left-arrow
      @click-left="$router.back()"
    />

    <section class="hero card-surface">
      <h2>两阶段导入</h2>
      <p>
        先解析目录结构，再标记作者层/作品层，最后提交导入。系统会在导入完成后自动清理缓冲目录；若中断，可继续当前会话。
      </p>
      <div class="hero-steps">
        <span>1. 导入源</span>
        <span>2. 标记层级</span>
        <span>3. 预览 JSON</span>
        <span>4. 提交入库</span>
      </div>
    </section>

    <section class="card-surface source-card">
      <div class="section-title">
        <h3>导入源</h3>
        <span class="hint">压缩包支持 `.zip/.rar/.7z`，支持任意层级嵌套解包</span>
      </div>

      <van-tabs v-model:active="sourceMode" animated>
        <van-tab name="upload" title="浏览器上传">
          <div class="source-panel">
            <div class="picker-row">
              <van-button type="primary" plain size="small" @click="triggerArchiveInput">
                选择压缩包
              </van-button>
              <van-tag type="primary" plain>{{ archiveFiles.length }} 个</van-tag>
            </div>

            <div class="picker-row">
              <van-button type="success" plain size="small" @click="triggerFolderInput">
                选择文件夹
              </van-button>
              <van-tag type="success" plain>{{ folderFiles.length }} 个文件</van-tag>
            </div>

            <div class="picker-tip">上传模式可用于局域网访问场景。</div>

            <input
              ref="archiveInputRef"
              type="file"
              multiple
              accept=".zip,.rar,.7z"
              class="hidden-input"
              @change="onArchiveFilesSelected"
            >
            <input
              ref="folderInputRef"
              type="file"
              multiple
              webkitdirectory
              directory
              class="hidden-input"
              @change="onFolderFilesSelected"
            >

            <van-button
              type="primary"
              block
              :loading="parsing"
              :disabled="parsing"
              @click="startUploadParse"
            >
              上传并解析
            </van-button>
          </div>
        </van-tab>

        <van-tab name="path" title="服务端路径">
          <div class="source-panel">
            <van-field
              v-model="sourcePath"
              label="本地路径"
              placeholder="例如 D:\\漫画\\合集 或 /data/comic.zip"
            />
            <div class="picker-tip">
              路径必须是服务器所在机器可访问路径。若你从局域网其他设备访问，通常请用“浏览器上传”。
            </div>
            <van-button
              type="primary"
              block
              :loading="parsing"
              :disabled="parsing"
              @click="startPathParse"
            >
              从路径解析
            </van-button>
          </div>
        </van-tab>
      </van-tabs>
    </section>

    <section class="card-surface session-card">
      <div class="session-grid">
        <div>
          <div class="label">会话 ID</div>
          <div class="value mono">{{ sessionId || '-' }}</div>
        </div>
        <div>
          <div class="label">清洗目录</div>
          <div class="value mono">{{ cleanRoot || '-' }}</div>
        </div>
        <div>
          <div class="label">当前选中</div>
          <div class="value mono">{{ selectedNode?.rel_path || '-' }}</div>
        </div>
      </div>
      <div class="session-actions">
        <van-button size="small" plain @click="clearCurrentSession" :disabled="!sessionId">清理会话</van-button>
      </div>
    </section>

    <section class="main-grid">
      <div class="card-surface tree-card">
        <div class="section-title">
          <h3>目录树</h3>
          <span class="hint">点击目录后，操作会作用到其同级目录（同一层）</span>
        </div>

        <div v-if="!treeRows.length" class="empty-block">尚未导入可解析目录。</div>
        <div v-else class="tree-list">
          <div
            v-for="row in treeRows"
            :key="row.id"
            class="tree-row"
            :class="{ selected: selectedNodeId === row.id }"
            :style="{ paddingLeft: `${12 + row.depth * 16}px` }"
            @click="selectNode(row.id)"
          >
            <button
              v-if="row.hasChildren"
              class="tree-toggle"
              @click.stop="toggleNode(row.id)"
            >
              {{ row.collapsed ? '▸' : '▾' }}
            </button>
            <span v-else class="tree-toggle placeholder">·</span>
            <span class="tree-name">{{ row.id === '.' ? '根目录' : row.real_name }}</span>
            <van-tag plain size="mini">总图 {{ row.total_images }}</van-tag>
            <van-tag v-if="row.direct_images > 0" plain size="mini">直图 {{ row.direct_images }}</van-tag>
            <van-tag v-if="row.role === 'author'" type="success" size="mini">作者目录</van-tag>
            <van-tag v-if="row.role === 'work'" type="primary" size="mini">作品目录</van-tag>
          </div>
        </div>
      </div>

      <div class="side-column">
        <div class="card-surface action-card">
          <div class="section-title">
            <h3>层级标记</h3>
          </div>
          <div class="selection-info">
            <template v-if="selectionLayerInfo">
              <div>当前目录：{{ selectedNode?.rel_path }}</div>
              <div>层父目录：{{ selectionLayerInfo.parent?.rel_path || '-' }}</div>
              <div>同层数量：{{ selectionLayerInfo.siblingCount }}</div>
              <div>当前状态：{{ roleText(selectionLayerInfo.role) }}</div>
            </template>
            <template v-else>
              请选择非根目录节点后再标记。
            </template>
          </div>
          <div class="action-buttons">
            <van-button type="success" plain size="small" @click="markLayer('author')">标记为作者层</van-button>
            <van-button type="primary" plain size="small" @click="markLayer('work')">标记为作品层</van-button>
            <van-button plain size="small" @click="clearCurrentLayer">清除此层</van-button>
            <van-button plain size="small" @click="clearAllLayers">清空全部标记</van-button>
          </div>
        </div>

        <div class="card-surface action-card">
          <div class="section-title">
            <h3>标记概览</h3>
          </div>
          <div v-if="assignmentEntries.length === 0" class="empty-block small">暂无标记。</div>
          <div v-else class="assignment-list">
            <div v-for="entry in assignmentEntries" :key="entry.parentId" class="assignment-item">
              <div class="assignment-title">{{ entry.parentRelPath }} → {{ roleText(entry.role) }}</div>
              <div class="hint">该层共 {{ entry.childCount }} 个目录</div>
            </div>
          </div>
        </div>

        <div class="card-surface action-card">
          <div class="section-title">
            <h3>导入警告</h3>
          </div>
          <div v-if="warnings.length === 0" class="empty-block small">暂无警告。</div>
          <div v-else class="warning-list">
            <div v-for="(warning, index) in warnings" :key="index" class="warning-item">{{ warning }}</div>
          </div>
        </div>
      </div>
    </section>

    <section class="card-surface result-card">
      <div class="section-title">
        <h3>结果与提交</h3>
      </div>
      <div class="result-actions">
        <van-button type="primary" @click="generateJson" :loading="exporting" :disabled="!sessionId">生成 JSON</van-button>
        <van-button plain @click="downloadJson" :disabled="!sessionId">下载 JSON</van-button>
        <van-button
          type="success"
          @click="commitImport"
          :loading="committing"
          :disabled="!sessionId"
        >
          提交导入
        </van-button>
      </div>
      <div class="commit-summary" v-if="commitSummary">
        <div>状态：{{ commitSummary.status }}</div>
        <div>成功：{{ commitSummary.imported_count }}</div>
        <div>跳过：{{ commitSummary.skipped_count }}</div>
        <div>失败：{{ commitSummary.failed_count }}</div>
      </div>
      <pre class="json-preview">{{ jsonPreviewText }}</pre>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { showFailToast, showSuccessToast, showToast } from 'vant'
import { comicApi } from '@/api'
import { useComicStore, useTagStore } from '@/stores'

const STORAGE_KEY = 'comic_local_import_session_v1'

const comicStore = useComicStore()
const tagStore = useTagStore()

const sourceMode = ref('upload')
const sourcePath = ref('')
const archiveFiles = ref([])
const folderFiles = ref([])

const archiveInputRef = ref(null)
const folderInputRef = ref(null)

const parsing = ref(false)
const exporting = ref(false)
const committing = ref(false)

const sessionId = ref('')
const cleanRoot = ref('')
const warnings = ref([])
const tree = ref(null)
const nodeMap = ref({})
const assignments = ref({})
const selectedNodeId = ref('')
const collapsedIds = ref(new Set())
const exportItems = ref([])
const commitSummary = ref(null)

const selectedNode = computed(() => {
  if (!selectedNodeId.value) return null
  return nodeMap.value[selectedNodeId.value] || null
})

const selectionLayerInfo = computed(() => {
  const node = selectedNode.value
  if (!node || node.parentId === null || !nodeMap.value[node.parentId]) return null
  const parent = nodeMap.value[node.parentId]
  return {
    parent,
    role: assignments.value[node.parentId] || '',
    siblingCount: Array.isArray(parent.childIds) ? parent.childIds.length : 0
  }
})

const assignmentEntries = computed(() => {
  return Object.entries(assignments.value)
    .map(([parentId, role]) => {
      const parent = nodeMap.value[parentId]
      return {
        parentId,
        role,
        parentRelPath: parent?.rel_path || parentId,
        childCount: Array.isArray(parent?.childIds) ? parent.childIds.length : 0
      }
    })
    .sort((a, b) => a.parentRelPath.localeCompare(b.parentRelPath, 'zh-CN'))
})

const treeRows = computed(() => {
  if (!tree.value) return []
  const rows = []
  const collapsed = collapsedIds.value

  const walk = (node, depth) => {
    const mapNode = nodeMap.value[node.id] || {}
    const hasChildren = Array.isArray(node.children) && node.children.length > 0
    const isCollapsed = collapsed.has(node.id)
    rows.push({
      ...node,
      depth,
      hasChildren,
      collapsed: isCollapsed,
      role: mapNode.parentId === null ? '' : (assignments.value[mapNode.parentId] || '')
    })
    if (hasChildren && !isCollapsed) {
      node.children.forEach((child) => walk(child, depth + 1))
    }
  }

  walk(tree.value, 0)
  return rows
})

const jsonPreviewText = computed(() => JSON.stringify(exportItems.value || [], null, 2))

function roleText(role) {
  if (role === 'author') return '作者层'
  if (role === 'work') return '作品层'
  return '未标记'
}

function rebuildNodeMap(treePayload) {
  const map = {}
  const walk = (node, parentId = null) => {
    map[node.id] = {
      ...node,
      parentId,
      childIds: Array.isArray(node.children) ? node.children.map((child) => child.id) : []
    }
    if (Array.isArray(node.children)) {
      node.children.forEach((child) => walk(child, node.id))
    }
  }
  walk(treePayload, null)
  nodeMap.value = map
}

function setImportedPayload(payload) {
  sessionId.value = payload.session_id || ''
  cleanRoot.value = payload.clean_root || ''
  warnings.value = Array.isArray(payload.warnings) ? payload.warnings : []
  tree.value = payload.tree || null
  exportItems.value = []
  commitSummary.value = null
  assignments.value = {}
  collapsedIds.value = new Set()

  if (tree.value) {
    rebuildNodeMap(tree.value)
    const firstChild = Array.isArray(tree.value.children) && tree.value.children[0]
    selectedNodeId.value = firstChild ? firstChild.id : tree.value.id
  } else {
    nodeMap.value = {}
    selectedNodeId.value = ''
  }
}

function persistSessionDraft() {
  if (!sessionId.value) {
    localStorage.removeItem(STORAGE_KEY)
    return
  }
  const payload = {
    sessionId: sessionId.value,
    assignments: assignments.value,
    selectedNodeId: selectedNodeId.value
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
}

async function restoreSessionDraft() {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return

  try {
    const draft = JSON.parse(raw)
    if (!draft?.sessionId) return

    const payload = await comicApi.localImportGetSessionTree(draft.sessionId)
    setImportedPayload(payload)

    if (draft.assignments && typeof draft.assignments === 'object') {
      assignments.value = { ...draft.assignments }
    }
    if (draft.selectedNodeId && nodeMap.value[draft.selectedNodeId]) {
      selectedNodeId.value = draft.selectedNodeId
    }
  } catch (error) {
    localStorage.removeItem(STORAGE_KEY)
  }
}

function triggerArchiveInput() {
  archiveInputRef.value?.click()
}

function triggerFolderInput() {
  folderInputRef.value?.click()
}

function onArchiveFilesSelected(event) {
  archiveFiles.value = Array.from(event?.target?.files || [])
}

function onFolderFilesSelected(event) {
  folderFiles.value = Array.from(event?.target?.files || [])
}

function clearRuntimeState() {
  sessionId.value = ''
  cleanRoot.value = ''
  warnings.value = []
  tree.value = null
  nodeMap.value = {}
  assignments.value = {}
  selectedNodeId.value = ''
  collapsedIds.value = new Set()
  exportItems.value = []
  commitSummary.value = null
  localStorage.removeItem(STORAGE_KEY)
}

async function startPathParse() {
  const path = sourcePath.value.trim()
  if (!path) {
    showFailToast('请输入服务端本地路径')
    return
  }

  parsing.value = true
  try {
    const payload = await comicApi.localImportCreateSessionFromPath(path)
    setImportedPayload(payload)
    showSuccessToast('解析完成')
  } catch (error) {
    showFailToast(error?.message || '解析失败')
  } finally {
    parsing.value = false
  }
}

function collectUploadSources() {
  const uploads = []
  const paths = []

  archiveFiles.value.forEach((file) => {
    uploads.push(file)
    paths.push(file.name)
  })

  folderFiles.value.forEach((file) => {
    uploads.push(file)
    const relativePath = (file.webkitRelativePath || '').trim()
    paths.push(relativePath || file.name)
  })

  return { uploads, paths }
}

async function startUploadParse() {
  const { uploads, paths } = collectUploadSources()
  if (!uploads.length) {
    showFailToast('请先选择压缩包或文件夹')
    return
  }

  parsing.value = true
  try {
    const payload = await comicApi.localImportCreateSessionFromUpload(uploads, paths)
    setImportedPayload(payload)
    showSuccessToast('上传解析完成')
  } catch (error) {
    showFailToast(error?.message || '上传解析失败')
  } finally {
    parsing.value = false
  }
}

function selectNode(nodeId) {
  selectedNodeId.value = nodeId
}

function toggleNode(nodeId) {
  const next = new Set(collapsedIds.value)
  if (next.has(nodeId)) {
    next.delete(nodeId)
  } else {
    next.add(nodeId)
  }
  collapsedIds.value = next
}

function markLayer(role) {
  const node = selectedNode.value
  if (!node || node.parentId === null) {
    showFailToast('请先选择非根目录节点')
    return
  }
  assignments.value = {
    ...assignments.value,
    [node.parentId]: role
  }
  commitSummary.value = null
}

function clearCurrentLayer() {
  const node = selectedNode.value
  if (!node || node.parentId === null) {
    showFailToast('请先选择可操作目录')
    return
  }
  if (!assignments.value[node.parentId]) {
    showToast('该层当前没有标记')
    return
  }
  const next = { ...assignments.value }
  delete next[node.parentId]
  assignments.value = next
  commitSummary.value = null
}

function clearAllLayers() {
  assignments.value = {}
  exportItems.value = []
  commitSummary.value = null
}

async function generateJson() {
  if (!sessionId.value) {
    showFailToast('请先创建解析会话')
    return
  }

  exporting.value = true
  try {
    const payload = await comicApi.localImportExport(sessionId.value, assignments.value)
    exportItems.value = Array.isArray(payload.items) ? payload.items : []
    showSuccessToast(`已生成 ${payload.count || 0} 条`) 
  } catch (error) {
    showFailToast(error?.message || '生成 JSON 失败')
  } finally {
    exporting.value = false
  }
}

async function downloadJson() {
  if (!sessionId.value) {
    showFailToast('请先创建解析会话')
    return
  }

  try {
    if (!exportItems.value.length) {
      await generateJson()
    }
    await comicApi.localImportDownloadResult(sessionId.value)
  } catch (error) {
    showFailToast(error?.message || '下载失败')
  }
}

async function commitImport() {
  if (!sessionId.value) {
    showFailToast('请先创建解析会话')
    return
  }

  committing.value = true
  try {
    const result = await comicApi.localImportCommit(sessionId.value, assignments.value)
    commitSummary.value = result

    if (Number(result.imported_count || 0) > 0) {
      await comicStore.fetchComics()
      await tagStore.fetchTags('comic')
    }

    if (Number(result.failed_count || 0) > 0) {
      showFailToast(`部分失败：成功 ${result.imported_count}，失败 ${result.failed_count}`)
    } else {
      showSuccessToast(`导入完成：${result.imported_count} 部`)
    }

    if (result.session_removed) {
      clearRuntimeState()
    }
  } catch (error) {
    showFailToast(error?.message || '提交导入失败')
  } finally {
    committing.value = false
  }
}

async function clearCurrentSession() {
  if (!sessionId.value) {
    clearRuntimeState()
    return
  }

  try {
    await comicApi.localImportClearSession(sessionId.value)
  } catch (_error) {
    // 忽略服务端清理失败，前端仍清理本地状态
  }
  clearRuntimeState()
  showSuccessToast('会话已清理')
}

watch([sessionId, assignments, selectedNodeId], () => {
  persistSessionDraft()
}, { deep: true })

onMounted(async () => {
  await restoreSessionDraft()
})
</script>

<style scoped>
.comic-local-import-page {
  min-height: 100vh;
  padding: 0 12px 80px;
  background: var(--surface-0);
}

.card-surface {
  margin-top: 12px;
  padding: 14px;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.hero h2 {
  margin: 0;
  font-size: 18px;
  color: var(--text-strong);
}

.hero p {
  margin: 10px 0 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.hero-steps {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hero-steps span {
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(89, 160, 255, 0.15);
  color: var(--brand-700);
  font-size: 12px;
}

.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.section-title h3 {
  margin: 0;
  font-size: 16px;
  color: var(--text-strong);
}

.hint {
  font-size: 12px;
  color: var(--text-tertiary);
}

.source-panel {
  padding: 8px 4px 4px;
}

.picker-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.picker-tip {
  margin: 8px 0 12px;
  color: var(--text-tertiary);
  line-height: 1.5;
  font-size: 12px;
}

.hidden-input {
  display: none;
}

.session-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.value {
  margin-top: 4px;
  color: var(--text-primary);
  line-height: 1.4;
  word-break: break-all;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
}

.session-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.main-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 1fr);
  gap: 12px;
  margin-top: 12px;
}

.tree-card {
  min-height: 560px;
}

.tree-list {
  max-height: 620px;
  overflow: auto;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  background: var(--surface-1);
  padding: 8px 0;
}

.tree-row {
  min-height: 34px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding-right: 10px;
  cursor: pointer;
}

.tree-row:hover {
  background: rgba(89, 160, 255, 0.1);
}

.tree-row.selected {
  background: rgba(89, 160, 255, 0.2);
  border-right: 2px solid var(--brand-600);
}

.tree-toggle {
  width: 20px;
  border: 0;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 0;
}

.tree-toggle.placeholder {
  text-align: center;
}

.tree-name {
  font-size: 13px;
  color: var(--text-primary);
  max-width: 260px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.side-column {
  display: grid;
  gap: 12px;
}

.selection-info {
  border: 1px dashed var(--border-soft);
  border-radius: 10px;
  padding: 10px;
  background: var(--surface-1);
  color: var(--text-secondary);
  line-height: 1.65;
  margin-bottom: 10px;
}

.action-buttons {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.assignment-list,
.warning-list {
  border: 1px dashed var(--border-soft);
  border-radius: 10px;
  background: var(--surface-1);
  padding: 10px;
}

.assignment-item,
.warning-item {
  padding: 6px 0;
  border-bottom: 1px solid var(--border-soft);
}

.assignment-item:last-child,
.warning-item:last-child {
  border-bottom: 0;
}

.assignment-title {
  color: var(--text-strong);
  font-size: 13px;
  margin-bottom: 2px;
}

.result-card {
  margin-top: 12px;
}

.result-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.commit-summary {
  margin-top: 10px;
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 13px;
}

.json-preview {
  margin-top: 10px;
  max-height: 320px;
  overflow: auto;
  border-radius: 10px;
  background: #0f172a;
  color: #e2e8f0;
  padding: 12px;
  font-size: 12px;
  line-height: 1.55;
}

.empty-block {
  border: 1px dashed var(--border-soft);
  border-radius: 10px;
  background: var(--surface-1);
  color: var(--text-tertiary);
  padding: 14px;
}

.empty-block.small {
  padding: 10px;
  font-size: 13px;
}

@media (max-width: 1080px) {
  .main-grid {
    grid-template-columns: 1fr;
  }

  .session-grid {
    grid-template-columns: 1fr;
  }

  .tree-name {
    max-width: 170px;
  }
}
</style>
