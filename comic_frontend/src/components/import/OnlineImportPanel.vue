<template>
  <div class="online-import-panel">
    <section class="panel-card">
      <div class="panel-header">
        <h3>{{ isVideoMode ? '通过 ID 导入视频' : '通过 ID 导入漫画' }}</h3>
        <p>创建在线任务后，可在「任务中心」里持续跟进进度。</p>
      </div>

      <div class="panel-section">
        <div class="option-title">导入方式</div>
        <div class="option-grid option-grid-two">
          <button
            type="button"
            class="option-card"
            :class="{ active: importType === 'by_id' }"
            @click="importType = 'by_id'"
          >
            <span class="option-card-title">{{ isVideoMode ? '通过 Code' : '通过 ID' }}</span>
            <span class="option-card-desc">输入单个标识，快速创建任务</span>
          </button>
          <button
            type="button"
            class="option-card"
            :class="{ active: importType === 'by_list' }"
            @click="importType = 'by_list'"
          >
            <span class="option-card-title">批量文件</span>
            <span class="option-card-desc">读取 `.txt` 清单，批量导入</span>
          </button>
        </div>
      </div>

      <div class="panel-section">
        <div class="option-title">导入位置</div>
        <div class="option-grid option-grid-two">
          <button
            type="button"
            class="option-card compact"
            :class="{ active: importTarget === 'home' }"
            @click="importTarget = 'home'"
          >
            <span class="option-card-title">本地库</span>
            <span class="option-card-desc">直接加入当前设备内容库</span>
          </button>
          <button
            type="button"
            class="option-card compact"
            :class="{ active: importTarget === 'recommendation' }"
            @click="importTarget = 'recommendation'"
          >
            <span class="option-card-title">预览库</span>
            <span class="option-card-desc">先进入预览区，再决定是否保留</span>
          </button>
        </div>
      </div>

      <div class="panel-section">
        <div class="option-title">来源平台</div>
        <div v-if="currentImportPlatforms.length > 0" class="option-grid option-grid-two">
          <button
            v-for="platform in currentImportPlatforms"
            :key="platform.value"
            type="button"
            class="option-card compact"
            :class="{ active: importPlatform === platform.value }"
            @click="importPlatform = platform.value"
          >
            <span class="option-card-title">{{ platform.label }}</span>
            <span class="option-card-desc">{{ isVideoMode ? '按平台视频标识导入' : '按平台作品标识导入' }}</span>
          </button>
        </div>
        <div v-else class="option-empty">当前模式暂无可用平台</div>
      </div>

      <van-cell-group inset class="panel-fields">
        <van-field
          v-if="importType === 'by_id'"
          v-model="importId"
          :label="isVideoMode ? 'Code' : 'ID'"
          :placeholder="isVideoMode ? '请输入视频 code（如 ARBB-048）' : '请输入内容ID'"
          clearable
        />
        <van-field
          v-else
          :model-value="importFile ? importFile.name : ''"
          label="文件"
          placeholder="选择 txt 文件"
          readonly
          @click="triggerImportFileInput"
        />
      </van-cell-group>

      <input
        ref="importFileInput"
        class="hidden-input"
        type="file"
        accept=".txt"
        @change="handleImportFileSelect"
      />

      <div class="panel-actions">
        <van-button type="primary" block round :loading="importing" @click="submit">
          创建导入任务
        </van-button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { showFailToast, showSuccessToast } from 'vant'

import { useImportTaskStore, useModeStore } from '@/stores'
import { fetchProtocolPlatformOptions } from '@/utils'

const modeStore = useModeStore()
const importTaskStore = useImportTaskStore()

const isVideoMode = computed(() => modeStore.isVideoMode)

const importType = ref('by_id')
const importTarget = ref('home')
const importPlatform = ref('')
const importId = ref('')
const importFile = ref(null)
const importing = ref(false)
const importPlatformOptions = ref([])
const importFileInput = ref(null)

const currentImportPlatforms = computed(() => importPlatformOptions.value)

async function loadImportPlatformOptions() {
  try {
    const options = await fetchProtocolPlatformOptions({
      mediaType: isVideoMode.value ? 'video' : 'comic',
      capability: 'catalog.search'
    })
    importPlatformOptions.value = options.map((item) => ({
      label: item.label,
      value: String(item.platform || '').trim().toUpperCase()
    }))
  } catch (error) {
    importPlatformOptions.value = []
    console.error('加载导入平台失败', error)
  }

  if (!importPlatformOptions.value.some((item) => item.value === importPlatform.value)) {
    importPlatform.value = importPlatformOptions.value[0]?.value || ''
  }
}

function triggerImportFileInput() {
  importFileInput.value?.click()
}

function handleImportFileSelect(event) {
  const file = event.target.files?.[0]
  if (file) importFile.value = file
}

function normalizeImportId(rawId, platform = '') {
  let id = String(rawId || '').trim()
  if (!id) return ''

  const normalizedPlatform = String(platform || '').toUpperCase()
  if (normalizedPlatform) {
    const platformPrefixRegex = new RegExp(`^${normalizedPlatform}_?`, 'i')
    id = id.replace(platformPrefixRegex, '')
  }

  return id.trim()
}

async function parseIdsFromFile(file, platform = '') {
  if (!file) {
    throw new Error('请先选择导入文件')
  }

  const content = await file.text()
  const ids = content
    .split(/[\r\n,\s]+/)
    .map((item) => normalizeImportId(item, platform))
    .filter(Boolean)

  return Array.from(new Set(ids))
}

function normalizeVideoCode(rawCode) {
  return String(rawCode || '').trim()
}

function canonicalizeVideoCode(rawCode) {
  return normalizeVideoCode(rawCode).replace(/-/g, '').toUpperCase()
}

async function parseVideoCodesFromFile(file) {
  if (!file) {
    throw new Error('请先选择导入文件')
  }

  const content = await file.text()
  const uniqueCodes = new Map()

  content
    .split(/[\r\n,\s]+/)
    .map((item) => normalizeVideoCode(item))
    .filter(Boolean)
    .forEach((code) => {
      const canonical = canonicalizeVideoCode(code)
      if (!canonical || uniqueCodes.has(canonical)) return
      uniqueCodes.set(canonical, code)
    })

  return Array.from(uniqueCodes.values())
}

async function handleComicImport() {
  const params = {
    import_type: importType.value,
    target: importTarget.value,
    platform: String(importPlatform.value || '').trim().toUpperCase(),
    content_type: 'comic',
    item_id: normalizeImportId(importId.value, importPlatform.value)
  }

  if (!params.platform) {
    throw new Error('当前模式暂无可用平台')
  }

  if (importType.value === 'by_id' && !params.item_id) {
    throw new Error('请输入漫画ID')
  }

  if (importType.value === 'by_list') {
    const comicIds = await parseIdsFromFile(importFile.value, importPlatform.value)
    if (comicIds.length === 0) {
      throw new Error('文件中没有可导入的ID')
    }
    params.item_ids = comicIds
    params.item_id = ''
  } else if (importType.value !== 'by_id') {
    throw new Error('当前模式不支持该导入方式')
  }

  await importTaskStore.createImportTask(params)
  showSuccessToast('任务已创建')
}

async function handleVideoImport() {
  const target = importTarget.value
  const defaultPlatform = String(importPlatform.value || '').trim().toUpperCase()

  if (!defaultPlatform) {
    throw new Error('当前模式暂无可用平台')
  }

  if (importType.value === 'by_id') {
    const videoCode = normalizeVideoCode(importId.value)
    if (!videoCode) {
      throw new Error('请输入视频 code')
    }
    const created = await importTaskStore.createImportTask({
      import_type: 'by_id',
      target,
      platform: defaultPlatform,
      item_id: videoCode,
      content_type: 'video'
    })
    if (!created) {
      throw new Error('创建导入任务失败')
    }
    showSuccessToast('任务已创建')
    return
  }

  if (importType.value === 'by_list') {
    const videoCodes = await parseVideoCodesFromFile(importFile.value)
    if (videoCodes.length === 0) {
      throw new Error('文件中没有可导入的 code')
    }
    const created = await importTaskStore.createImportTask({
      import_type: 'by_list',
      target,
      platform: defaultPlatform,
      item_ids: videoCodes,
      content_type: 'video'
    })
    if (!created) {
      throw new Error('创建导入任务失败')
    }
    showSuccessToast('任务已创建')
  } else {
    throw new Error('当前模式不支持该导入方式')
  }
}

async function submit() {
  importing.value = true
  try {
    if (isVideoMode.value) {
      await handleVideoImport()
    } else {
      await handleComicImport()
    }
  } catch (error) {
    showFailToast(error?.message || '操作失败')
  } finally {
    importing.value = false
  }
}

watch(() => modeStore.currentMode, async () => {
  importId.value = ''
  importFile.value = null
  await loadImportPlatformOptions()
})

onMounted(() => {
  loadImportPlatformOptions()
})
</script>

<style scoped>
.online-import-panel {
  padding: 12px 0 24px;
}

.panel-card {
  margin: 0 16px;
  padding: 20px;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.panel-header {
  margin-bottom: 18px;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
  color: var(--text-strong);
}

.panel-header p {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-tertiary);
}

.panel-section {
  margin-bottom: 18px;
}

.option-title {
  margin-bottom: 8px;
  font-size: 14px;
  color: var(--text-secondary);
}

.option-grid {
  display: grid;
  gap: 10px;
}

.option-grid-two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.option-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  padding: 12px;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  background: var(--surface-1);
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.18s ease, background-color 0.18s ease, box-shadow 0.18s ease;
}

.option-card.compact {
  min-height: 88px;
}

.option-card.active {
  border-color: rgba(47, 116, 255, 0.5);
  background: rgba(89, 160, 255, 0.14);
  box-shadow: 0 12px 20px rgba(47, 116, 255, 0.12);
}

.option-card-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-strong);
}

.option-card-desc {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-tertiary);
}

.option-empty {
  font-size: 13px;
  color: var(--text-tertiary);
}

.panel-fields {
  margin: 0 0 4px;
  overflow: hidden;
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  background: var(--surface-1);
}

.hidden-input {
  display: none;
}

.panel-actions {
  margin-top: 18px;
}

@media (max-width: 767px) {
  .panel-card {
    margin-inline: 10px;
    padding: 16px;
  }
}
</style>
