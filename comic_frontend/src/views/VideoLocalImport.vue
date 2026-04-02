<template>
  <div class="video-local-import-page desktop-page-shell">
    <van-nav-bar
      title="本地视频导入"
      left-arrow
      @click-left="$router.back()"
    />

    <section class="card-surface intro-card">
      <h2>服务端路径导入</h2>
      <p>
        仅支持输入服务端本机“文件夹路径”。系统会递归扫描常见视频文件并导入到本地库。
        你可以选择软连接（保留源文件）或硬链接（移动源文件），系统会自动忽略压缩包与非视频文件。
      </p>
    </section>

    <section class="card-surface form-card">
      <van-field
        v-model="sourcePath"
        label="目录路径"
        placeholder="例如 D:\\Videos\\LOCAL"
        clearable
      />
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
      <div v-if="importMode === 'hardlink_move'" class="mode-tip danger-tip">
        已启用硬链接导入（移动源文件）：将直接移动源目录中的视频文件，请先确认路径和备份。
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
import { videoApi } from '@/api'
import { useVideoStore } from '@/stores'

const videoStore = useVideoStore()

const sourcePath = ref('')
const importing = ref(false)
const result = ref(null)
const importMode = ref('hardlink_move')

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
      importMode: importMode.value
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

.intro-card h2 {
  margin: 0;
  font-size: 18px;
  color: var(--text-strong);
}

.intro-card p {
  margin: 10px 0 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.import-mode-switch {
  margin: 10px 0;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  background: var(--surface-1);
  padding: 10px 12px;
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

.section-title h3 {
  margin: 0;
  font-size: 16px;
  color: var(--text-strong);
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
