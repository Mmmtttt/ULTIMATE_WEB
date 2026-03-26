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
        <span>3. 提交入库</span>
      </div>
    </section>

    <section class="card-surface source-card">
      <div class="section-title">
        <h3>导入源</h3>
        <span class="hint">压缩包支持 `.zip/.rar/.7z`，支持任意层级嵌套解包</span>
      </div>

      <div class="mode-toggle" role="tablist" aria-label="导入源切换">
        <button
          class="mode-btn"
          :class="{ active: sourceMode === 'upload' }"
          @click="sourceMode = 'upload'"
        >
          从设备上传（推荐）
        </button>
        <button
          class="mode-btn"
          :class="{ active: sourceMode === 'path' }"
          @click="sourceMode = 'path'"
        >
          服务端路径导入
        </button>
      </div>

      <div v-if="sourceMode === 'upload'" class="source-panel">
        <div class="picker-row">
          <van-button type="primary" plain size="small" @click="triggerArchiveInput">
            选择压缩包
          </van-button>
          <van-tag type="primary" plain>{{ archiveFiles.length }} 个</van-tag>
        </div>

        <div class="picker-tip">
          上传模式仅支持压缩包，这是跨设备访问服务器时最稳定的方式。
        </div>

        <input
          ref="archiveInputRef"
          type="file"
          multiple
          accept=".zip,.rar,.7z"
          class="hidden-input"
          @change="onArchiveFilesSelected"
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

      <div v-else class="source-panel">
        <van-field
          v-model="sourcePath"
          label="本地路径"
          placeholder="例如 D:\\漫画\\合集 或 /data/comic.zip"
        />
        <div class="picker-row compact">
          <van-button plain size="small" @click="triggerPathArchivePicker">选择压缩包路径</van-button>
          <van-button plain size="small" @click="triggerPathFolderPicker">选择文件夹路径</van-button>
        </div>
        <div class="picker-tip">
          路径模式可导入服务端本机上的压缩包或文件夹。
        </div>
        <input
          ref="pathArchivePickerRef"
          type="file"
          accept=".zip,.rar,.7z"
          class="hidden-input"
          @change="onPathArchivePicked"
        >
        <input
          ref="pathFolderPickerRef"
          type="file"
          multiple
          webkitdirectory
          directory
          class="hidden-input"
          @change="onPathFolderPicked"
        >
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
          <span class="hint">点击目录后，会按当前标记模式作用到该目录所在层</span>
        </div>

        <div class="mark-mode-row">
          <button class="mark-mode-btn" :class="{ active: markMode === 'author' }" @click="markMode = 'author'">
            标记为作者层
          </button>
          <button class="mark-mode-btn" :class="{ active: markMode === 'work' }" @click="markMode = 'work'">
            标记为作品层
          </button>
          <button class="mark-mode-btn" :class="{ active: markMode === 'clear' }" @click="markMode = 'clear'">
            清除此层
          </button>
        </div>

        <div v-if="!treeRows.length" class="empty-block">尚未导入可解析目录。</div>
        <div v-else class="tree-list">
          <div
            v-for="row in treeRows"
            :key="row.id"
            class="tree-row"
            :class="{ selected: selectedNodeId === row.id }"
            :style="{ paddingLeft: `${12 + row.depth * 16}px` }"
            @click="onTreeNodeClick(row.id)"
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
            <van-tag plain size="mini">图片数量 {{ row.total_images }}</van-tag>
            <van-tag v-if="row.role === 'author'" type="success" size="mini">作者目录</van-tag>
            <van-tag v-if="row.role === 'work'" type="primary" size="mini">作品目录</van-tag>
          </div>
        </div>
        <div class="tree-footer-actions">
          <van-button plain size="small" @click="restoreDefaultLayers">恢复默认标记</van-button>
          <van-button plain size="small" @click="clearAllLayers">清空全部标记</van-button>
        </div>
      </div>

      <div class="side-column">
        <div class="card-surface action-card">
          <div class="section-title">
            <h3>层级标记</h3>
          </div>
          <div class="selection-info">
            <template v-if="selectionLayerInfo">
              <div>当前模式：{{ markModeText }}</div>
              <div>当前目录：{{ selectedNode?.rel_path }}</div>
              <div>层父目录：{{ selectionLayerInfo.parent?.rel_path || '-' }}</div>
              <div>同层数量：{{ selectionLayerInfo.siblingCount }}</div>
              <div>当前状态：{{ roleText(selectionLayerInfo.role) }}</div>
            </template>
            <template v-else>
              当前模式：{{ markModeText }}，请点击目录树中的目录节点。
            </template>
          </div>
          <div class="action-buttons">
            <span class="hint">提示：新标记会自动清理同一路径上的冲突旧标记。</span>
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
        <h3>提交导入</h3>
      </div>
      <div class="result-actions">
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

const archiveInputRef = ref(null)
const pathArchivePickerRef = ref(null)
const pathFolderPickerRef = ref(null)

const parsing = ref(false)
const committing = ref(false)

const sessionId = ref('')
const cleanRoot = ref('')
const warnings = ref([])
const tree = ref(null)
const nodeMap = ref({})
const assignments = ref({})
const selectedNodeId = ref('')
const collapsedIds = ref(new Set())
const commitSummary = ref(null)
const markMode = ref('work')

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

const markModeText = computed(() => {
  if (markMode.value === 'author') return '标记为作者层'
  if (markMode.value === 'work') return '标记为作品层'
  if (markMode.value === 'clear') return '清除此层'
  return '未选择'
})

function roleText(role) {
  if (role === 'author') return '作者层'
  if (role === 'work') return '作品层'
  return '未标记'
}

function getNodeDepth(nodeId) {
  let depth = 0
  let currentId = nodeId
  while (currentId && currentId !== '.') {
    const node = nodeMap.value[currentId]
    if (!node || node.parentId === null || node.parentId === undefined) {
      break
    }
    depth += 1
    currentId = node.parentId
  }
  return depth
}

function isChapterLikeName(name) {
  const raw = String(name || '').trim()
  if (!raw) return false

  const compact = raw
    .replace(/[【】\[\]（）()]/g, '')
    .replace(/[_\-\s]/g, '')
    .toLowerCase()

  if (!compact) return false

  const basicTokenPattern = /^(?:\d{1,4}|[a-z]{1,2}|[ivxlcdm]{1,6}|[一二三四五六七八九十百千零〇两]{1,6})$/
  if (basicTokenPattern.test(compact)) return true

  const chapterPattern = /^(?:第)?(?:\d{1,4}|[a-z]{1,2}|[ivxlcdm]{1,6}|[一二三四五六七八九十百千零〇两]{1,6})(?:话|章|回|节|卷|集|部)?$/
  if (chapterPattern.test(compact)) return true

  const englishChapterPattern = /^(?:ch|chap|chapter|ep|episode|vol|volume)[\divxlcdm\-_.]{1,8}$/
  if (englishChapterPattern.test(compact)) return true

  return false
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

function buildDefaultAssignments() {
  const rootNode = nodeMap.value['.']
  if (!rootNode) return {}

  const rootHasDirectImages = Number(rootNode.direct_images || 0) > 0
  const rootHasChildren = Array.isArray(rootNode.childIds) && rootNode.childIds.length > 0

  // 深度很短：根目录下就是直图，默认根目录为作品层（无作者）
  if (rootHasDirectImages && !rootHasChildren) {
    return { '.': 'work' }
  }

  let defaults = { '.': 'author' }
  const directImageNodes = Object.values(nodeMap.value)
    .filter((node) => node.id !== '.' && Number(node.direct_images || 0) > 0)
    .sort((a, b) => getNodeDepth(b.id) - getNodeDepth(a.id))

  for (const imageParentNode of directImageNodes) {
    let workNode = imageParentNode
    if (isChapterLikeName(imageParentNode.real_name) && imageParentNode.parentId && nodeMap.value[imageParentNode.parentId]) {
      workNode = nodeMap.value[imageParentNode.parentId]
    }

    const targetParentId = workNode.parentId === null ? workNode.id : workNode.parentId
    defaults = applyLayerMarkWithConstraints(targetParentId, 'work', defaults)
  }

  if (rootHasDirectImages) {
    defaults = applyLayerMarkWithConstraints('.', 'work', defaults)
  }

  return defaults
}

function setImportedPayload(payload) {
  sessionId.value = payload.session_id || ''
  cleanRoot.value = payload.clean_root || ''
  warnings.value = Array.isArray(payload.warnings) ? payload.warnings : []
  tree.value = payload.tree || null
  commitSummary.value = null
  collapsedIds.value = new Set()

  if (tree.value) {
    rebuildNodeMap(tree.value)
    assignments.value = buildDefaultAssignments()
    const firstChild = Array.isArray(tree.value.children) && tree.value.children[0]
    selectedNodeId.value = firstChild ? firstChild.id : tree.value.id
  } else {
    nodeMap.value = {}
    assignments.value = {}
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
    selectedNodeId: selectedNodeId.value,
    markMode: markMode.value
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
    if (['author', 'work', 'clear'].includes(draft.markMode)) {
      markMode.value = draft.markMode
    }
  } catch (error) {
    localStorage.removeItem(STORAGE_KEY)
  }
}

function triggerArchiveInput() {
  archiveInputRef.value?.click()
}

function triggerPathArchivePicker() {
  pathArchivePickerRef.value?.click()
}

function triggerPathFolderPicker() {
  pathFolderPickerRef.value?.click()
}

function onArchiveFilesSelected(event) {
  archiveFiles.value = Array.from(event?.target?.files || [])
}

function normalizeInputPath(rawPath) {
  return String(rawPath || '').trim().replaceAll('\\\\', '/')
}

function deriveFolderPathFromPickedFile(file) {
  const absPath = normalizeInputPath(file?.path)
  const relativePath = normalizeInputPath(file?.webkitRelativePath)
  if (!absPath || !relativePath) return ''

  const lowerAbs = absPath.toLowerCase()
  const lowerRel = relativePath.toLowerCase()
  if (!lowerAbs.endsWith(lowerRel)) return ''

  const base = absPath.slice(0, absPath.length - relativePath.length).replace(/\/+$/, '')
  return base
}

function readCandidatePathFromFile(file, inputValue) {
  const filePath = normalizeInputPath(file?.path)
  if (filePath) return filePath

  const rawInput = normalizeInputPath(inputValue)
  if (rawInput && !rawInput.toLowerCase().includes('/fakepath/')) {
    return rawInput
  }
  return ''
}

function onPathArchivePicked(event) {
  const file = event?.target?.files?.[0]
  if (!file) return

  const candidate = readCandidatePathFromFile(file, event?.target?.value)
  if (candidate) {
    sourcePath.value = candidate
    showSuccessToast('已填充压缩包路径')
    return
  }

  showToast('当前浏览器无法读取绝对路径，请手动粘贴服务端路径')
}

function onPathFolderPicked(event) {
  const file = event?.target?.files?.[0]
  if (!file) return

  const folderPath = deriveFolderPathFromPickedFile(file) || readCandidatePathFromFile(file, event?.target?.value)
  if (folderPath) {
    sourcePath.value = folderPath
    showSuccessToast('已填充文件夹路径')
    return
  }

  showToast('当前浏览器无法读取绝对路径，请手动粘贴服务端路径')
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
  commitSummary.value = null
  markMode.value = 'work'
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

function isAncestorOrSame(ancestorId, nodeId) {
  if (!ancestorId || !nodeId) return false
  let currentId = nodeId
  while (currentId !== null && currentId !== undefined) {
    if (currentId === ancestorId) return true
    const currentNode = nodeMap.value[currentId]
    if (!currentNode) break
    currentId = currentNode.parentId
  }
  return false
}

function getLayerNodeIds(parentId) {
  const parent = nodeMap.value[parentId]
  if (!parent || !Array.isArray(parent.childIds)) return []
  return parent.childIds
}

function hasLayerPathConflict(existingParentId, targetParentId) {
  const existingNodeIds = getLayerNodeIds(existingParentId)
  const targetNodeIds = getLayerNodeIds(targetParentId)
  if (!existingNodeIds.length || !targetNodeIds.length) return false

  for (const existingNodeId of existingNodeIds) {
    for (const targetNodeId of targetNodeIds) {
      if (
        isAncestorOrSame(existingNodeId, targetNodeId) ||
        isAncestorOrSame(targetNodeId, existingNodeId)
      ) {
        return true
      }
    }
  }
  return false
}

function getLayerOrder(existingParentId, targetParentId) {
  const existingNodeIds = getLayerNodeIds(existingParentId)
  const targetNodeIds = getLayerNodeIds(targetParentId)

  let existingAboveTarget = false
  let targetAboveExisting = false

  for (const existingNodeId of existingNodeIds) {
    for (const targetNodeId of targetNodeIds) {
      if (isAncestorOrSame(existingNodeId, targetNodeId)) {
        existingAboveTarget = true
      }
      if (isAncestorOrSame(targetNodeId, existingNodeId)) {
        targetAboveExisting = true
      }
      if (existingAboveTarget && targetAboveExisting) {
        return {
          existingAboveTarget: true,
          targetAboveExisting: true
        }
      }
    }
  }

  return {
    existingAboveTarget,
    targetAboveExisting
  }
}

function shouldRemoveExistingMark(existingRole, newRole, existingParentId, targetParentId) {
  if (!hasLayerPathConflict(existingParentId, targetParentId)) {
    return false
  }

  if (existingRole === newRole) {
    return true
  }

  const order = getLayerOrder(existingParentId, targetParentId)

  // 合法关系：作者在上，作品在下
  if (existingRole === 'author' && newRole === 'work') {
    return !order.existingAboveTarget
  }
  if (existingRole === 'work' && newRole === 'author') {
    return !order.targetAboveExisting
  }

  return true
}

function applyLayerMarkWithConstraints(targetParentId, role, baseAssignments = assignments.value) {
  const next = { ...baseAssignments }
  if (role === 'clear') {
    delete next[targetParentId]
    return next
  }

  Object.entries(next).forEach(([existingParentId, existingRole]) => {
    if (existingParentId === targetParentId) return
    if (shouldRemoveExistingMark(existingRole, role, existingParentId, targetParentId)) {
      delete next[existingParentId]
    }
  })

  next[targetParentId] = role
  return next
}

function applyMarkModeToNode(nodeId) {
  const node = nodeMap.value[nodeId]
  if (!node) {
    return
  }

  const parentId = node.parentId === null ? node.id : node.parentId
  const next = applyLayerMarkWithConstraints(parentId, markMode.value)
  assignments.value = next
  commitSummary.value = null
}

function onTreeNodeClick(nodeId) {
  selectNode(nodeId)
  applyMarkModeToNode(nodeId)
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

function clearAllLayers() {
  assignments.value = {}
  commitSummary.value = null
}

function restoreDefaultLayers() {
  assignments.value = buildDefaultAssignments()
  commitSummary.value = null
  showSuccessToast('已恢复默认标记')
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
      comicStore.clearCache('list')
      comicStore.clearCache('detail')
      await comicStore.fetchComics(true)
      await tagStore.fetchTags('comic', true)
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

watch([sessionId, assignments, selectedNodeId, markMode], () => {
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

.mode-toggle {
  display: inline-flex;
  width: 100%;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  overflow: hidden;
  background: var(--surface-1);
  margin-bottom: 10px;
}

.mode-btn {
  border: 0;
  flex: 1;
  background: transparent;
  color: var(--text-secondary);
  padding: 8px 10px;
  cursor: pointer;
  transition: all var(--motion-fast) var(--ease-standard);
  font-size: 12px;
}

.mode-btn + .mode-btn {
  border-left: 1px solid var(--border-soft);
}

.mode-btn.active {
  background: linear-gradient(140deg, rgba(89, 160, 255, 0.2), rgba(63, 132, 234, 0.12));
  color: var(--brand-700);
}

.picker-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.picker-row.compact {
  justify-content: flex-start;
  gap: 8px;
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

.tree-footer-actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
}

.mark-mode-row {
  display: inline-flex;
  width: 100%;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  overflow: hidden;
  background: var(--surface-1);
  margin-bottom: 10px;
}

.mark-mode-btn {
  border: 0;
  flex: 1;
  background: transparent;
  color: var(--text-secondary);
  padding: 8px 10px;
  cursor: pointer;
  font-size: 12px;
  transition: all var(--motion-fast) var(--ease-standard);
}

.mark-mode-btn + .mark-mode-btn {
  border-left: 1px solid var(--border-soft);
}

.mark-mode-btn.active {
  background: linear-gradient(140deg, rgba(89, 160, 255, 0.24), rgba(63, 132, 234, 0.1));
  color: var(--brand-700);
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
  display: flex;
  justify-content: flex-start;
  align-items: center;
  min-height: 24px;
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
