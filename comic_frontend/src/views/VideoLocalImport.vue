<template>
  <div class="video-local-import-page desktop-page-shell">
    <van-nav-bar
      title="本地视频导入"
      left-arrow
      @click-left="$router.back()"
    />

    <section class="hero card-surface">
      <h2>一步导入</h2>
      <p>
        仅支持输入服务端本机“文件夹路径”。系统会递归扫描常见视频文件并导入到本地库。
        你可以决定按单个视频导入，还是按叶子目录合并为多集作品。
        你可以选择软连接（保留源文件）或硬链接（移动源文件），系统会自动忽略压缩包与非视频文件。
      </p>
      <div class="hero-steps">
        <span>1. 填写路径</span>
        <span>2. 选择导入策略</span>
        <span>3. 执行并查看结果</span>
      </div>
    </section>

    <section class="card-surface form-card">
      <div class="section-title">
        <h3>导入源</h3>
        <span class="hint">仅支持服务端本机绝对路径</span>
      </div>

      <van-field
        v-model="sourcePath"
        label="本地路径"
        placeholder="例如 D:\\Videos\\LOCAL"
        clearable
      >
        <template #right-icon>
          <DirectoryPicker v-model="sourcePath" />
        </template>
      </van-field>

      <div class="import-mode-switch">
        <div class="switch-main">
          <span class="switch-side" :class="{ active: importMode === 'hardlink_move' }">硬链接</span>
          <van-switch
            v-model="isSoftlinkMode"
            size="20px"
          />
          <span class="switch-side" :class="{ active: importMode === 'softlink_ref' }">软连接</span>
        </div>
        <div class="switch-desc">
          {{ importMode === 'softlink_ref' ? '软连接：保留源文件，直接引用源路径播放' : '硬链接：移动源文件到本地库目录' }}
        </div>
      </div>

      <div class="picker-tip">
        路径模式会递归扫描常见视频文件；默认每个视频独立导入，也可以切换成按叶子目录合并。
      </div>

      <div class="grouping-mode-switch">
        <div class="section-title inline-title">
          <h3>导入粒度</h3>
          <span class="hint">默认逐文件导入</span>
        </div>
        <div class="grouping-mode-buttons">
          <van-button
            size="small"
            :type="groupingMode === 'per_file' ? 'primary' : 'default'"
            class="grouping-button"
            @click="groupingMode = 'per_file'"
          >
            每个视频单独导入
          </van-button>
          <van-button
            size="small"
            :type="groupingMode === 'leaf_dir' ? 'primary' : 'default'"
            class="grouping-button"
            @click="groupingMode = 'leaf_dir'"
          >
            叶子目录合并为多集
          </van-button>
        </div>
        <div class="switch-desc">
          {{ groupingMode === 'per_file'
            ? '逐文件导入：每个视频默认是一个独立条目；识别到相同番号时，会并入已有本地视频并作为新分集。'
            : '叶子目录合并：同一叶子目录中的视频会优先按番号拆组，其余未识别番号的视频会合并为一个多集条目。'
          }}
        </div>
      </div>

      <div v-if="importMode === 'hardlink_move'" class="mode-tip danger-tip">
        已启用硬链接导入（移动源文件）：将直接移动源目录中的视频文件，请先确认路径和备份。
      </div>

      <div v-else class="mode-tip">
        已启用软连接导入：源文件会保留在原目录，系统只建立引用关系，适合已有整理好的媒体库。
      </div>

      <van-button
        type="primary"
        block
        :loading="importing"
        :disabled="importing"
        @click="runImport"
      >
        开始导入
      </van-button>
    </section>

    <section v-if="result" class="card-surface result-card">
      <div class="section-title">
        <h3>导入结果</h3>
      </div>
      <div class="summary">{{ result.summary || '导入完成' }}</div>
      <div class="stats-grid">
        <div class="stat-item">
          <div class="label">扫描文件</div>
          <div class="value">{{ result.scanned_files || 0 }}</div>
        </div>
        <div class="stat-item">
          <div class="label">视频文件</div>
          <div class="value">{{ result.scanned_video_files || 0 }}</div>
        </div>
        <div class="stat-item">
          <div class="label">成功导入</div>
          <div class="value success">{{ result.imported_count || 0 }}</div>
        </div>
        <div class="stat-item">
          <div class="label">跳过</div>
          <div class="value warning">{{ result.skipped_count || 0 }}</div>
        </div>
        <div class="stat-item">
          <div class="label">失败</div>
          <div class="value danger">{{ result.failed_count || 0 }}</div>
        </div>
      </div>

      <van-cell-group v-if="previewSkippedItems.length" inset title="部分跳过项">
        <van-cell
          v-for="(item, index) in previewSkippedItems"
          :key="`skipped-${index}`"
          :title="item.file || '-'"
          :label="item.reason || ''"
        />
      </van-cell-group>

      <van-cell-group v-if="previewFailedItems.length" inset title="部分失败项">
        <van-cell
          v-for="(item, index) in previewFailedItems"
          :key="`failed-${index}`"
          :title="item.file || '-'"
          :label="item.reason || ''"
        />
      </van-cell-group>
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { closeToast, showConfirmDialog, showFailToast, showLoadingToast, showSuccessToast } from 'vant'
import DirectoryPicker from '@/components/common/DirectoryPicker.vue'
import { videoApi } from '@/api'
import { useVideoStore } from '@/stores'

const videoStore = useVideoStore()

const sourcePath = ref('')
const importing = ref(false)
const result = ref(null)
const importMode = ref('hardlink_move')
const groupingMode = ref('per_file')

const isSoftlinkMode = computed({
  get: () => importMode.value === 'softlink_ref',
  set: (enabled) => {
    importMode.value = enabled ? 'softlink_ref' : 'hardlink_move'
  }
})

const previewSkippedItems = computed(() => {
  const items = Array.isArray(result.value?.skipped_items) ? result.value.skipped_items : []
  return items.slice(0, 20)
})

const previewFailedItems = computed(() => {
  const items = Array.isArray(result.value?.failed_items) ? result.value.failed_items : []
  return items.slice(0, 20)
})

async function runImport() {
  const path = String(sourcePath.value || '').trim()
  if (!path) {
    showFailToast('请输入服务端目录路径')
    return
  }

  if (importMode.value === 'hardlink_move') {
    try {
      await showConfirmDialog({
        title: '风险提示',
        message: '硬链接导入会移动源文件，若路径填写错误可能导致源目录文件变化，是否继续？',
        confirmButtonText: '继续',
        cancelButtonText: '取消'
      })
    } catch {
      return
    }
  }

  importing.value = true
  showLoadingToast({
    message: '正在导入本地视频...',
    forbidClick: true,
    duration: 0
  })

  try {
    const response = await videoApi.localImportFromPath(path, {
      importMode: importMode.value,
      groupingMode: groupingMode.value
    })
    closeToast()
    if (response?.code !== 200) {
      showFailToast(response?.msg || '导入失败')
      return
    }

    result.value = response.data || {}
    await videoStore.fetchList()
    showSuccessToast('导入任务执行完成')
  } catch (error) {
    closeToast()
    showFailToast(error?.message || '导入失败')
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.video-local-import-page {
  min-height: 95vh;
  background: transparent;
  padding-bottom: 80px;
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
  align-items: center;
  justify-content: space-between;
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

.import-mode-switch {
  margin: 10px 0;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  background: var(--surface-1);
  padding: 10px 12px;
}

.grouping-mode-switch {
  margin: 10px 0;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  background: var(--surface-1);
  padding: 10px 12px;
}

.inline-title {
  margin-bottom: 8px;
}

.grouping-mode-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.grouping-button {
  min-width: 156px;
}

.switch-main {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.switch-side {
  font-size: 13px;
  color: var(--text-tertiary);
  transition: color var(--motion-fast) var(--ease-standard);
}

.switch-side.active {
  color: var(--text-primary);
  font-weight: 600;
}

.switch-desc {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.45;
}

.mode-tip {
  margin: 8px 0 12px;
  color: var(--text-tertiary);
  line-height: 1.5;
  font-size: 12px;
}

.danger-tip {
  color: #9a3412;
}

.picker-tip {
  margin: 8px 0 12px;
  color: var(--text-tertiary);
  line-height: 1.5;
  font-size: 12px;
}

.summary {
  margin-top: 10px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.stats-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}

.stat-item {
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  padding: 10px;
  background: var(--surface-1);
}

.stat-item .label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.stat-item .value {
  margin-top: 6px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.stat-item .value.success {
  color: #0f8a35;
}

.stat-item .value.warning {
  color: #a56200;
}

.stat-item .value.danger {
  color: #b42318;
}

@media (max-width: 1080px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
