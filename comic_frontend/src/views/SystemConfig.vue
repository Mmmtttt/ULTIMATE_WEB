<template>
  <div class="system-config desktop-page-shell">
    <van-nav-bar title="系统设置" left-text="返回" left-arrow @click-left="$router.back()" />

    <section class="settings-section">
      <div class="section-heading">
        <div>
          <span class="section-kicker">READER EXPERIENCE</span>
          <h2>阅读体验</h2>
        </div>
        <span class="section-note">常用设置</span>
      </div>
      <van-cell-group inset class="config-group settings-card">
        <div class="select-row" @click.stop="toggleDropdown('pageMode', $event)">
          <div class="setting-copy">
            <span class="select-label">默认翻页模式</span>
            <span class="setting-description">可选择上下翻页、左→右或右→左翻页</span>
          </div>
          <span class="select-value">{{ pageModeLabel }} <van-icon name="arrow-down" size="12" /></span>
        </div>
        <van-cell title="单页浏览" label="开启后阅读页每次仅显示一页内容（可继续缩放、滑动与翻页）">
          <template #right-icon>
            <van-switch v-model="singlePageBrowsingValue" @change="updateSinglePageBrowsing" />
          </template>
        </van-cell>
        <div class="select-row" @click.stop="toggleDropdown('background', $event)">
          <div class="setting-copy">
            <span class="select-label">默认背景色</span>
            <span class="setting-description">应用于漫画阅读页的默认背景</span>
          </div>
          <span class="select-value">{{ backgroundLabel }} <van-icon name="arrow-down" size="12" /></span>
        </div>
      </van-cell-group>
    </section>

    <section class="settings-section">
      <div class="section-heading">
        <div>
          <span class="section-kicker">LIBRARY & CONTENT</span>
          <h2>列表与内容</h2>
        </div>
        <span class="section-note">显示设置</span>
      </div>
      <van-cell-group inset class="config-group settings-card">
        <van-cell title="内容模式" label="切换漫画与视频的内容模式">
          <template #right-icon>
            <ModeSwitch class="settings-mode-switch" />
          </template>
        </van-cell>
        <van-cell
          v-if="isMobile"
          title="悬浮切换按钮"
          label="在页面上显示可拖拽的漫画/视频切换按钮，点击切换、拖动移动、松手吸附到屏幕边缘"
        >
          <template #right-icon>
            <van-switch
              :model-value="configStore.showFloatingModeSwitch"
              @update:model-value="updateFloatingModeSwitch"
            />
          </template>
        </van-cell>
        <div class="select-row" @click.stop="toggleDropdown('pageSize', $event)">
          <div class="setting-copy">
            <span class="select-label">列表分页数量</span>
            <span class="setting-description">本地库、预览库等列表的默认分页数量</span>
          </div>
          <span class="select-value">{{ pageSizeLabel }} <van-icon name="arrow-down" size="12" /></span>
        </div>
        <van-cell
          title="预览库导入自动下载资源"
          label="开启后导入到预览库时将自动异步下载高清封面和预览视频（无预览视频时自动跳过）"
        >
          <template #right-icon>
            <van-switch v-model="autoDownloadPreviewImportAssets" @change="updatePreviewImportAssetDownload" />
          </template>
        </van-cell>
      </van-cell-group>
    </section>

    <section v-if="semanticSupported" class="settings-section">
      <div class="section-heading">
        <div>
          <span class="section-kicker">SEARCH ENGINE</span>
          <h2>检索方式</h2>
        </div>
        <span class="section-note">桌面端可选</span>
      </div>
      <van-cell-group inset class="config-group settings-card">
        <van-cell
          title="语义检索"
          label="开启后本地库搜关键词改用语义索引排序；关闭时保持默认的索引查询方式"
        >
          <template #right-icon>
            <van-switch
              :model-value="searchEngine === 'semantic'"
              :loading="savingSearchEngine"
              @update:model-value="updateSearchEngine"
            />
          </template>
        </van-cell>
        <div v-if="searchEngine === 'semantic'" class="semantic-panel">
          <div class="semantic-line">
            <span>索引状态</span>
            <strong>{{ semanticIndexLabel }}</strong>
          </div>
          <div class="semantic-line">
            <span>已入库</span>
            <strong>{{ semanticIndex.doc_count || 0 }} 本</strong>
          </div>
          <div class="semantic-line">
            <span>梗概 / 速览覆盖</span>
            <strong>{{ semanticIndex.vibe_covered || 0 }} / {{ semanticIndex.catalog_covered || 0 }}</strong>
          </div>
          <div class="semantic-line">
            <span>标签词表</span>
            <strong>{{ semanticIndex.tag_vocabulary || 0 }} 条（含同义词）</strong>
          </div>
          <div class="semantic-line">
            <span>向量召回</span>
            <strong>{{ semanticVectorLabel }}</strong>
          </div>
          <div class="semantic-line">
            <span>关键词索引</span>
            <strong>{{ semanticKeywordLabel }}</strong>
          </div>
          <p class="semantic-note">{{ semanticHint }}</p>
          <van-button
            size="small"
            type="primary"
            round
            plain
            :loading="rebuildingSemantic || semanticRebuildingState"
            :disabled="semanticRebuildingState"
            @click="rebuildSemanticIndex"
          >
            重建语义索引
          </van-button>
        </div>
        <details class="config-disclosure">
          <summary class="config-disclosure-summary">
            <span class="disclosure-icon"><van-icon name="photograph" size="17" /></span>
            <span class="disclosure-copy">
              <strong>识图补全（多模态模型）</strong>
              <small>{{ visionSummary }}</small>
            </span>
            <van-icon name="arrow" size="16" class="disclosure-chevron" />
          </summary>
          <div class="disclosure-body">
            <p class="disclosure-note">
              读封面与目录页 → 模型写气质梗概 / 收录速览 / 标签 → 生成草稿；确认后才写回漫画。
            </p>
            <div class="vision-field">
              <span class="vision-field-label">服务商预设</span>
              <select class="vision-select" :value="visionProviderId" @change="applyVisionProvider">
                <option value="">自定义 / 手动填写</option>
                <option v-for="provider in visionProviders" :key="provider.id" :value="provider.id">
                  {{ provider.name }}{{ provider.vision ? '' : '（不支持图片输入）' }}
                </option>
              </select>
            </div>
            <p v-if="visionProvider?.note" class="vision-provider-note">{{ visionProvider.note }}</p>
            <div v-if="visionProvider" class="vision-endpoint">
              <span>接口地址</span>
              <code>{{ visionForm.base_url }}</code>
            </div>
            <van-field
              v-else
              v-model="visionForm.base_url"
              label="Base URL"
              placeholder="https://api.example.com/v1"
            />
            <van-field
              v-model="visionForm.api_key"
              type="password"
              label="API Key"
              :placeholder="visionKeyPlaceholder"
              autocomplete="off"
              @blur="refreshVisionModels"
            />
            <div class="vision-field">
              <span class="vision-field-label">模型</span>
              <select v-if="visionModelOptions.length" v-model="visionForm.model" class="vision-select">
                <option v-for="model in visionModelOptions" :key="model" :value="model">{{ model }}</option>
              </select>
              <van-field v-else v-model="visionForm.model" placeholder="例如 Qwen/Qwen2.5-VL-72B-Instruct" />
              <van-button
                size="mini"
                plain
                round
                :loading="loadingVisionModels"
                @click="refreshVisionModels"
              >
                刷新
              </van-button>
            </div>
            <p v-if="visionModelHint" class="vision-provider-note">{{ visionModelHint }}</p>
            <van-field v-model.number="visionForm.max_gap" type="digit" label="采样间隔上限" placeholder="1-8 页" />
            <van-field v-model.number="visionForm.max_images" type="digit" label="单本最多图片" placeholder="1-96 张" />
            <div class="vision-context">
              <div class="vision-context-copy">
                <span class="vision-field-label">识图前附带的上下文文件</span>
                <code class="vision-context-path">{{ visionContextLabel }}</code>
              </div>
              <van-switch
                :model-value="visionForm.context_enabled"
                size="20px"
                @update:model-value="val => { visionForm.context_enabled = !!val }"
              />
            </div>
            <p class="vision-provider-note">
              文件内容会作为 system 消息先于图片发送；改文件即刻生效，保存配置后重新生成草稿即可。
              若页面出现明显未成年角色，任务里固定追加的硬性要求会优先于该文件，不生成性化描述。
            </p>
            <div class="inline-actions single">
              <van-button type="primary" block round :loading="savingVision" @click="saveVisionConfig">
                保存识图配置
              </van-button>
            </div>
          </div>
        </details>
        <div class="vision-batch">
          <div class="vision-batch-head">
            <strong>批量补全</strong>
            <span>{{ visionBatchSummary }}</span>
          </div>
          <div v-if="visionBatch.total" class="vision-batch-bar">
            <i :style="{ width: visionBatchPercent + '%' }"></i>
          </div>
          <p v-if="visionBatchUsage" class="vision-provider-note">{{ visionBatchUsage }}</p>
          <div class="vision-batch-actions">
            <van-button
              size="mini"
              type="primary"
              round
              :loading="Boolean(visionBatch.running)"
              :disabled="Boolean(visionBatch.running) || !visionMissingCount"
              @click="startVisionBatchAll"
            >
              批量补全缺失（{{ visionMissingCount }} 本）
            </van-button>
            <van-button
              v-if="visionBatch.running"
              size="mini"
              plain
              round
              @click="stopVisionBatchRun"
            >
              停止
            </van-button>
          </div>
          <p class="vision-provider-note">
            逐本排队跑识图，结果进「待确认草稿」；跑完不会自动写回。顺序按页数从少到多。
          </p>
        </div>
        <div v-if="visionFailures.length" class="vision-failures">
          <div class="vision-batch-head">
            <strong>识图失败</strong>
            <span>{{ visionFailures.length }} 本 · 失败原因见下</span>
          </div>
          <div v-for="failure in visionFailures" :key="failure.comic_id" class="vision-failure">
            <div class="vision-draft-head">
              <strong>{{ failure.title || failure.comic_id }}</strong>
              <span class="vision-draft-meta">{{ failure.at }}</span>
            </div>
            <p class="vision-failure-error">{{ failure.error }}</p>
            <div class="vision-draft-actions">
              <van-button size="mini" type="primary" round @click="retryVisionDraft(failure)">重试</van-button>
              <van-button size="mini" plain round @click="clearVisionFailure(failure)">清除</van-button>
            </div>
          </div>
        </div>
        <div v-if="visionDrafts.length" class="vision-drafts">
          <div v-for="draft in visionDrafts" :key="draft.comic_id" class="vision-draft">
            <div class="vision-draft-head">
              <strong>{{ draft.current_title || draft.title || draft.comic_id }}</strong>
              <span class="vision-draft-meta">{{ draft.sampled_count || 0 }} 页 · {{ draft.model }}</span>
            </div>
            <p class="vision-draft-text">{{ draft.draft?.vibe || '（没有梗概）' }}</p>
            <p class="vision-draft-text secondary">{{ draft.draft?.catalog || '（没有速览）' }}</p>
            <p class="vision-draft-tags">{{ draftTagText(draft) }}</p>
            <p v-if="draftUsageText(draft)" class="vision-draft-meta">{{ draftUsageText(draft) }}</p>
            <div class="vision-draft-actions">
              <van-button size="mini" type="primary" round @click="applyVisionDraft(draft)">写回</van-button>
              <van-button size="mini" plain round @click="discardVisionDraft(draft)">丢弃</van-button>
            </div>
          </div>
        </div>
      </van-cell-group>
    </section>

    <section class="settings-section settings-section--compact">
      <div class="section-heading">
        <div>
          <span class="section-kicker">PLATFORM</span>
          <h2>平台与诊断</h2>
        </div>
      </div>
      <van-cell-group inset class="config-group settings-card">
        <van-cell
          title="Debug 日志模式"
          label="开启后记录更完整的诊断日志；关闭时保留错误和重要操作日志。"
        >
          <template #right-icon>
            <van-switch v-model="debugModeValue" @change="updateDebugMode" />
          </template>
        </van-cell>
        <van-cell
          v-if="isNormalSpace"
          title="第三方平台配置"
          label="管理搜索、导入和补全信息使用的平台"
          is-link
          to="/config/third-party"
        />
      </van-cell-group>
    </section>

    <section class="settings-section settings-section--advanced">
      <div class="section-heading">
        <div>
          <span class="section-kicker">SERVICE & DATA</span>
          <h2>服务与数据</h2>
        </div>
        <span class="section-note">高级设置</span>
      </div>

      <details class="config-disclosure">
        <summary class="config-disclosure-summary">
          <span class="disclosure-icon"><van-icon name="lock" size="17" /></span>
          <span class="disclosure-copy">
            <strong>项目密码</strong>
            <small>{{ canChangeProjectPassword ? '正常空间可修改登录密码' : '仅正常空间可修改' }}</small>
          </span>
          <van-icon name="arrow" size="16" class="disclosure-chevron" />
        </summary>
        <div class="disclosure-body">
          <p class="disclosure-note">保存后新密码立即用于后续登录，不会显示当前密码。</p>
          <van-field
            v-model="projectPassword"
            type="password"
            label="新密码"
            placeholder="请输入新的登录密码"
            autocomplete="new-password"
          />
          <van-field
            v-model="projectPasswordConfirm"
            type="password"
            label="确认密码"
            placeholder="再次输入新密码"
            autocomplete="new-password"
          />
          <div class="inline-actions single">
            <van-button
              type="primary"
              block
              round
              :disabled="!canChangeProjectPassword"
              :loading="savingProjectPassword"
              @click="saveProjectPassword"
            >
              {{ canChangeProjectPassword ? '保存项目密码' : '仅正常空间可修改' }}
            </van-button>
          </div>
        </div>
      </details>

      <details class="config-disclosure">
        <summary class="config-disclosure-summary">
          <span class="disclosure-icon"><van-icon name="folder-o" size="17" /></span>
          <span class="disclosure-copy">
            <strong>数据目录配置</strong>
            <small>{{ runtimeDataDir || '正在读取当前运行目录' }}</small>
          </span>
          <van-icon name="arrow" size="16" class="disclosure-chevron" />
        </summary>
        <div class="disclosure-body">
          <p class="disclosure-note">修改后会重启后端；迁移模式会同时移动当前 data 目录内容。</p>
          <div class="path-summary-grid">
            <div class="path-summary-card">
              <span class="path-summary-label">当前运行目录</span>
              <code class="path-summary-value">{{ runtimeDataDir || '读取中...' }}</code>
            </div>
            <div v-if="resolvedDataDir && resolvedDataDir !== runtimeDataDir" class="path-summary-card emphasis">
              <span class="path-summary-label">待生效目录</span>
              <code class="path-summary-value">{{ resolvedDataDir }}</code>
            </div>
          </div>
          <van-field
            v-model="systemDataDir"
            label="data_dir"
            placeholder="例如 ./comic_backend/data 或 D:\\MyData\\ULTIMATE"
          />
          <div class="inline-actions">
            <van-button
              type="primary"
              block
              round
              :loading="savingSystemConfigMode === 'migrate'"
              @click="saveSystemDataDirWithMigration"
            >
              保存并迁移 data 目录
            </van-button>
            <van-button
              plain
              type="primary"
              block
              round
              class="secondary-action"
              :loading="savingSystemConfigMode === 'rebind'"
              @click="saveSystemDataDirWithoutMigration"
            >
              仅保存 data 目录路径
            </van-button>
          </div>
        </div>
      </details>

      <details class="config-disclosure">
        <summary class="config-disclosure-summary">
          <span class="disclosure-icon"><van-icon name="setting-o" size="17" /></span>
          <span class="disclosure-copy">
            <strong>配置文件目录</strong>
            <small>{{ selectedConfigDir || runtimeConfigDir || '正在读取当前配置目录' }}</small>
          </span>
          <van-icon name="arrow" size="16" class="disclosure-chevron" />
        </summary>
        <div class="disclosure-body">
          <p class="disclosure-note">会迁移 server_config.json 与 third_party_config.json，并在保存后自动重启后端。</p>
          <div class="path-summary-grid">
            <div class="path-summary-card">
              <span class="path-summary-label">当前运行目录</span>
              <code class="path-summary-value">{{ runtimeConfigDir || '读取中...' }}</code>
            </div>
            <div v-if="selectedConfigDir" class="path-summary-card" :class="{ emphasis: selectedConfigDir !== runtimeConfigDir }">
              <span class="path-summary-label">{{ selectedConfigDir === runtimeConfigDir ? '当前选中目录' : '重启后生效目录' }}</span>
              <code class="path-summary-value">{{ selectedConfigDir }}</code>
            </div>
            <div class="path-summary-card">
              <span class="path-summary-label">默认目录 / 来源</span>
              <code class="path-summary-value">{{ defaultConfigDir || '-' }}</code>
              <span class="path-summary-meta">来源：{{ configDirSourceLabel }}</span>
            </div>
          </div>
          <van-field
            v-model="configDirInput"
            label="config_dir"
            placeholder="例如 C:\\Users\\用户名\\AppData\\Roaming\\ULTIMATE_WEB"
          />
          <div class="inline-actions">
            <van-button
              type="primary"
              block
              round
              :loading="savingConfigDir"
              @click="saveConfigDir"
            >
              保存配置目录并迁移配置文件
            </van-button>
          </div>
        </div>
      </details>
    </section>

    <div class="action-area">
      <van-button type="danger" block round @click="confirmReset">
        重置为默认设置
      </van-button>
    </div>

    <div class="mmmtttt-config">github@Mmmtttt</div>

    <Teleport to="body">
      <div
        v-if="activeDropdown"
        class="select-dropdown-overlay"
        :style="dropdownStyle"
        @click.stop
      >
        <div
          v-for="opt in activeDropdownColumns"
          :key="opt.value"
          class="select-option"
          :class="{ active: activeDropdownValue === opt.value }"
          @click="onDropdownSelect(opt.value)"
        >{{ opt.text }}</div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'

import { comicApi } from '@/api/comic'
import { configApi } from '@/api/config'
import { semanticApi } from '@/api/semantic'
import { reloadPage } from '@/runtime/browser'
import { useAuthStore, useConfigStore, useRuntimeStore } from '@/stores'
import ModeSwitch from '@/components/common/ModeSwitch.vue'
import { useDevice } from '@/composables/useDevice'

const configStore = useConfigStore()
const authStore = useAuthStore()
const runtimeStore = useRuntimeStore()
const { isMobile } = useDevice()

const pageModeValue = ref('up_down')
const singlePageBrowsingValue = ref(false)
const backgroundValue = ref('white')
const autoDownloadPreviewImportAssets = ref(true)
const pageSizeValue = ref(20)
const leftRightReadingReversedValue = ref(false)
const debugModeValue = ref(false)
const pageSizeOptions = [20, 40, 60]

// ---------- 检索方式（语义检索：仅桌面端可选） ----------
const searchEngine = ref('catalog')
const semanticStatus = ref({})
const savingSearchEngine = ref(false)
const rebuildingSemantic = ref(false)

const semanticSupported = computed(() => !runtimeStore.isMobileCore)
const semanticIndex = computed(() => semanticStatus.value?.index || {})
const semanticRebuildingState = computed(() => Boolean(semanticStatus.value?.rebuild?.running))
const semanticIndexLabel = computed(() => {
  if (semanticRebuildingState.value) return '构建中…'
  if (!semanticIndex.value.indexed) return '尚未建立'
  if (semanticIndex.value.stale) return '已过期（下次搜索自动重建）'
  return `已就绪 · ${String(semanticIndex.value.built_at || '').replace('T', ' ')}`
})
const semanticVectorLabel = computed(() => {
  if (!semanticIndex.value.embedder_available) return '不可用'
  if (!semanticIndex.value.vector_enabled) return `模型就绪（${semanticIndex.value.embed_dim || 0} 维）· 待重建`
  return `已启用 · ${semanticIndex.value.embed_dim || 0} 维`
})
const semanticKeywordLabel = computed(() => (
  semanticIndex.value.search_index === 'fts5_trigram_like' ? 'FTS5 trigram' : 'LIKE 扫描'
))
const semanticHint = computed(() => {
  if (!semanticIndex.value.embedder_available) {
    return '未安装 fastembed：语义检索目前只有「标签 + 关键词」两路。需要向量召回时安装 comic_backend/requirements-semantic.txt 后重建索引。'
  }
  if (!semanticIndex.value.vector_enabled) {
    return '向量模型可用，点一次「重建语义索引」即可启用向量召回。'
  }
  const total = Number(semanticIndex.value.doc_count || 0)
  const covered = Number(semanticIndex.value.vibe_covered || 0)
  if (total > 0 && covered < total) {
    return `标签、关键词、向量三路按 RRF 融合。还有 ${total - covered} 本没有气质梗概（vibe），这几本的向量只从标题与标签里取信息。`
  }
  return '标签、关键词、向量三路结果按 RRF 融合排序；未建索引时自动回落到原来的关键词匹配。'
})

async function refreshSemanticStatus() {
  if (!semanticSupported.value) return
  try {
    const res = await semanticApi.getStatus()
    if (res?.code === 200) {
      semanticStatus.value = res.data || {}
    }
  } catch {
    semanticStatus.value = {}
  }
}

async function loadSemanticState() {
  if (!semanticSupported.value) return
  try {
    const res = await configApi.get()
    if (res?.code === 200 && res.data) {
      searchEngine.value = String(res.data.search_engine || 'catalog').toLowerCase()
    }
  } catch {
    searchEngine.value = 'catalog'
  }
  await refreshSemanticStatus()
}

async function updateSearchEngine(value) {
  const next = value ? 'semantic' : 'catalog'
  savingSearchEngine.value = true
  try {
    const res = await configApi.update({ search_engine: next })
    if (res?.code === 200) {
      searchEngine.value = next
      showSuccessToast(next === 'semantic' ? '已切换到语义检索' : '已切回默认检索')
      await refreshSemanticStatus()
    } else {
      showFailToast(res?.msg || '切换检索方式失败')
    }
  } catch {
    showFailToast('切换检索方式失败')
  } finally {
    savingSearchEngine.value = false
  }
}

async function rebuildSemanticIndex() {
  rebuildingSemantic.value = true
  try {
    const res = await semanticApi.rebuild(true)
    if (res?.code !== 200) {
      showFailToast(res?.msg || '重建语义索引失败')
      return
    }
    // 后台构建：轮询状态直到结束（首次带向量可能要下载模型）
    const deadline = Date.now() + 10 * 60 * 1000
    let finished = false
    while (Date.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve, 1500))
      await refreshSemanticStatus()
      const rebuildState = semanticStatus.value?.rebuild || {}
      if (!rebuildState.running) {
        finished = true
        if (rebuildState.error) {
          showFailToast(`重建失败：${rebuildState.error}`)
        } else {
          showSuccessToast('语义索引已重建')
        }
        break
      }
    }
    if (!finished) {
      showFailToast('重建仍在后台进行，可稍后回到本页查看状态')
    }
  } catch {
    showFailToast('重建语义索引失败')
  } finally {
    rebuildingSemantic.value = false
  }
}

// ---------- 识图补全（VLM 草稿） ----------
const visionForm = ref({ base_url: '', model: '', api_key: '', max_gap: 8, max_images: 48, context_enabled: true })
const visionStatus = ref({})
const visionDrafts = ref([])
const savingVision = ref(false)
const visionProviders = ref([])
const visionProviderId = ref('')
const visionLiveModels = ref([])
const loadingVisionModels = ref(false)
const visionModelHint = ref('')
const visionMissing = ref([])
const visionFailures = ref([])
const visionBatch = ref({ running: false, total: 0, done: 0, failed: 0, current: '', error: '', items: [] })
let visionBatchTimer = null

const visionMissingCount = computed(() => visionMissing.value.length)
const visionBatchPercent = computed(() => {
  const total = Number(visionBatch.value?.total || 0)
  if (!total) return 0
  const finished = Number(visionBatch.value?.done || 0) + Number(visionBatch.value?.failed || 0)
  return Math.min(100, Math.round((finished / total) * 100))
})
const visionBatchSummary = computed(() => {
  const batch = visionBatch.value || {}
  if (!batch.total) return '暂无需要补全的漫画'
  if (batch.running) {
    return `进行中 ${(batch.done || 0) + (batch.failed || 0)}/${batch.total}${batch.current ? ' · ' + batch.current : ''}`
  }
  const failed = Number(batch.failed || 0)
  return `已完成 ${batch.done || 0}/${batch.total}${failed ? ` · 失败 ${failed}` : ''}`
})
const visionBatchUsage = computed(() => {
  const usage = visionBatch.value?.usage || {}
  const promptTokens = Number(usage.prompt_tokens || 0)
  if (!promptTokens) return ''
  const cached = Number(usage.cached_tokens || 0)
  const percent = Math.round((cached / promptTokens) * 100)
  return `输入 ${promptTokens} tokens · 缓存命中 ${percent}%（${cached}）`
})

function draftUsageText(draft) {
  const usage = draft?.usage || {}
  const promptTokens = Number(usage.prompt_tokens || 0)
  if (!promptTokens) return ''
  const cached = Number(usage.cached_tokens || 0)
  return `${promptTokens} tokens · 缓存命中 ${Math.round((cached / promptTokens) * 100)}%`
}

const visionProvider = computed(() => visionProviders.value.find(item => item.id === visionProviderId.value) || null)
const visionModelOptions = computed(() => {
  const source = visionLiveModels.value.length
    ? visionLiveModels.value
    : ((visionProvider.value?.models) || [])
  const models = [...source]
  const current = String(visionForm.value.model || '').trim()
  if (current && !models.includes(current)) {
    models.unshift(current)
  }
  return models
})
const visionContext = computed(() => visionStatus.value?.context || {})
const visionContextLabel = computed(() => {
  const ctx = visionContext.value
  if (!ctx.path) return '未找到内置上下文文件'
  if (!ctx.exists) return `文件缺失：${ctx.path}`
  return `${ctx.chars || 0} 字 · ${ctx.path}`
})

function applyVisionProvider(event) {
  const id = typeof event === 'string' ? event : event?.target?.value
  visionProviderId.value = id || ''
  visionLiveModels.value = []
  visionModelHint.value = ''
  const provider = visionProviders.value.find(item => item.id === visionProviderId.value)
  if (!provider) return
  visionForm.value.base_url = provider.base_url
  visionForm.value.model = (provider.models || [])[0] || ''
  if (visionForm.value.api_key || visionStatus.value?.configured) {
    refreshVisionModels()
  }
}

async function refreshVisionModels() {
  if (!semanticSupported.value || loadingVisionModels.value) return
  loadingVisionModels.value = true
  visionModelHint.value = ''
  try {
    const res = await semanticApi.fetchVisionModels({
      base_url: visionForm.value.base_url,
      api_key: visionForm.value.api_key,
    })
    if (res?.code === 200) {
      const data = res.data || {}
      visionLiveModels.value = data.models || []
      if (data.live) {
        visionModelHint.value = `已从接口拉取 ${visionLiveModels.value.length} 个模型`
        if (!visionForm.value.model && visionLiveModels.value.length) {
          visionForm.value.model = visionLiveModels.value[0]
        }
      } else {
        visionModelHint.value = data.error ? `拉取失败：${data.error}（显示预设模型）` : '显示预设模型'
      }
    } else {
      visionModelHint.value = res?.msg || '拉取模型列表失败'
    }
  } catch {
    visionModelHint.value = '拉取模型列表失败'
  } finally {
    loadingVisionModels.value = false
  }
}

const visionSummary = computed(() => (
  visionStatus.value?.configured ? `已配置 · ${visionStatus.value.model}` : '未配置'
))
const visionKeyPlaceholder = computed(() => (
  visionStatus.value?.configured ? '已保存；留空表示不修改' : 'sk-...'
))

function draftTagText(draft) {
  const tags = (draft.draft?.tags || []).map(tag => tag.name).filter(Boolean)
  return tags.length ? tags.join('、') : '（没有标签）'
}

async function loadVisionState() {
  if (!semanticSupported.value) return
  try {
    const res = await configApi.get()
    const vision = res?.code === 200 ? (res.data?.vision_config || {}) : {}
    visionForm.value = {
      base_url: vision.base_url || '',
      model: vision.model || '',
      api_key: '',
      max_gap: vision.max_gap || 8,
      max_images: vision.max_images || 48,
      context_enabled: vision.context_enabled !== false,
    }
    const matched = visionProviders.value.find(item => item.base_url === visionForm.value.base_url)
    visionProviderId.value = matched?.id || ''
  } catch {
    // 读取失败时保留表单原值
  }
  try {
    const res = await semanticApi.listDrafts()
    if (res?.code === 200) {
      visionDrafts.value = res.data?.drafts || []
      visionFailures.value = res.data?.failures || []
      visionStatus.value = res.data?.status || {}
    }
  } catch {
    visionDrafts.value = []
  }
}

async function retryVisionDraft(failure) {
  const comicId = failure?.comic_id
  if (!comicId) return
  try {
    const started = await semanticApi.createDraft(comicId)
    if (started?.code !== 200) {
      showFailToast(started?.msg || '重试失败')
      return
    }
    showSuccessToast('已重新开始识图')
    const deadline = Date.now() + 5 * 60 * 1000
    while (Date.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve, 3000))
      const res = await semanticApi.getDraft(comicId)
      const data = res?.data || {}
      if (data.draft) {
        showSuccessToast('草稿已生成')
        break
      }
      const state = data.state || {}
      if (!state.running && data.failure) {
        showFailToast(`仍然失败：${data.failure.error}`)
        break
      }
    }
    await Promise.all([loadVisionState(), loadVisionMissing(), refreshSemanticStatus()])
  } catch {
    showFailToast('重试失败')
  }
}

async function clearVisionFailure(failure) {
  try {
    const res = await semanticApi.clearVisionFailure(failure.comic_id)
    if (res?.code === 200) {
      await loadVisionState()
    }
  } catch {
    showFailToast('清除失败')
  }
}

async function loadVisionProviders() {
  if (!semanticSupported.value) return
  try {
    const res = await semanticApi.getVisionProviders()
    if (res?.code === 200) {
      visionProviders.value = res.data?.providers || []
      if (res.data?.context) {
        visionStatus.value = { ...visionStatus.value, context: res.data.context }
      }
    }
  } catch {
    visionProviders.value = []
  }
}

async function loadVisionMissing() {
  if (!semanticSupported.value) return
  try {
    const res = await semanticApi.listVisionMissing(true)
    if (res?.code === 200) {
      visionMissing.value = res.data?.items || []
    }
  } catch {
    visionMissing.value = []
  }
}

async function loadVisionBatch() {
  if (!semanticSupported.value) return
  try {
    const res = await semanticApi.getVisionBatch()
    if (res?.code === 200) {
      visionBatch.value = res.data || visionBatch.value
      if (visionBatch.value?.running) {
        startVisionBatchPolling()
      }
    }
  } catch {
    // 忽略
  }
}

function startVisionBatchPolling() {
  if (visionBatchTimer) return
  visionBatchTimer = setInterval(async () => {
    try {
      const res = await semanticApi.getVisionBatch()
      if (res?.code === 200) {
        visionBatch.value = res.data || visionBatch.value
      }
      if (!visionBatch.value?.running) {
        stopVisionBatchPolling()
        await Promise.all([loadVisionState(), loadVisionMissing(), refreshSemanticStatus()])
      }
    } catch {
      // 单次失败不打断轮询
    }
  }, 3000)
}

function stopVisionBatchPolling() {
  if (visionBatchTimer) {
    clearInterval(visionBatchTimer)
    visionBatchTimer = null
  }
}

async function startVisionBatchAll() {
  try {
    const res = await semanticApi.startVisionBatch({ only_missing: true })
    if (res?.code === 200) {
      visionBatch.value = res.data || visionBatch.value
      if (visionBatch.value?.running) {
        showSuccessToast(`已开始批量补全 ${visionBatch.value.total} 本`)
        startVisionBatchPolling()
      } else {
        showFailToast(res?.msg || '没有需要补全的漫画')
      }
    } else {
      showFailToast(res?.msg || '启动批量补全失败')
    }
  } catch {
    showFailToast('启动批量补全失败')
  }
}

async function stopVisionBatchRun() {
  try {
    const res = await semanticApi.stopVisionBatch()
    if (res?.code === 200) {
      showSuccessToast('已请求停止，当前这本跑完就停')
    }
  } catch {
    showFailToast('停止失败')
  }
}

async function saveVisionConfig() {
  savingVision.value = true
  try {
    const payload = {
      base_url: visionForm.value.base_url,
      model: visionForm.value.model,
      max_gap: visionForm.value.max_gap,
      max_images: visionForm.value.max_images,
      context_enabled: visionForm.value.context_enabled,
    }
    if (String(visionForm.value.api_key || '').trim()) {
      payload.api_key = visionForm.value.api_key
    }
    const res = await configApi.update({ vision_config: payload })
    if (res?.code === 200) {
      showSuccessToast('识图配置已保存')
      await loadVisionState()
      if (payload.api_key) {
        visionForm.value.api_key = ''
      }
      await refreshVisionModels()
    } else {
      showFailToast(res?.msg || '保存识图配置失败')
    }
  } catch {
    showFailToast('保存识图配置失败')
  } finally {
    savingVision.value = false
  }
}

async function applyVisionDraft(draft) {
  try {
    const res = await semanticApi.applyDraft(draft.comic_id)
    if (res?.code === 200) {
      showSuccessToast('已写回漫画元数据')
      await loadVisionState()
      await refreshSemanticStatus()
    } else {
      showFailToast(res?.msg || '写回失败')
    }
  } catch {
    showFailToast('写回失败')
  }
}

async function discardVisionDraft(draft) {
  try {
    const res = await semanticApi.deleteDraft(draft.comic_id)
    if (res?.code === 200) {
      showSuccessToast('草稿已丢弃')
      await loadVisionState()
    }
  } catch {
    showFailToast('丢弃草稿失败')
  }
}

const activeDropdown = ref('')
const dropdownPos = ref({ top: 0, left: 0, width: 0 })

const dropdownStyle = computed(() => ({
  top: `${dropdownPos.value.top}px`,
  left: `${dropdownPos.value.left}px`,
  minWidth: `${dropdownPos.value.width}px`,
}))

const pageModeColumns = [
  { text: '上下翻页', value: 'up_down' },
  { text: '左→右翻页', value: 'left_right' },
  { text: '右→左翻页', value: 'left_right_reversed' },
]

const pageSizeColumns = pageSizeOptions.map(s => ({ text: `每页 ${s} 条`, value: s }))

const backgroundColumns = [
  { text: '白色背景', value: 'white' },
  { text: '深色背景', value: 'dark' },
  { text: '护眼色背景', value: 'sepia' },
]

const dropdownColumnMap = {
  pageMode: pageModeColumns,
  pageSize: pageSizeColumns,
  background: backgroundColumns,
}

const pageModeSelection = computed(() => {
  if (pageModeValue.value !== 'left_right') return 'up_down'
  return leftRightReadingReversedValue.value ? 'left_right_reversed' : 'left_right'
})

const dropdownValueMap = computed(() => ({
  pageMode: pageModeSelection.value,
  pageSize: pageSizeValue.value,
  background: backgroundValue.value,
}))

const activeDropdownColumns = computed(() => dropdownColumnMap[activeDropdown.value] || [])
const activeDropdownValue = computed(() => dropdownValueMap.value[activeDropdown.value])

const backgroundMap = { white: '白色背景', dark: '深色背景', sepia: '护眼色背景' }

const pageModeLabel = computed(() => {
  const selected = pageModeColumns.find(option => option.value === pageModeSelection.value)
  return selected?.text || '上下翻页'
})
const pageSizeLabel = computed(() => `每页 ${pageSizeValue.value} 条`)
const backgroundLabel = computed(() => backgroundMap[backgroundValue.value] || backgroundValue.value)

const systemDataDir = ref('')
const runtimeDataDir = ref('')
const resolvedDataDir = ref('')
const savingSystemConfigMode = ref('')
const configDirInput = ref('')
const runtimeConfigDir = ref('')
const selectedConfigDir = ref('')
const defaultConfigDir = ref('')
const configDirSource = ref('')
const savingConfigDir = ref(false)
const projectPassword = ref('')
const projectPasswordConfirm = ref('')
const savingProjectPassword = ref(false)
const isNormalSpace = computed(() => !authStore.enabled || authStore.mode === 'normal')
const canChangeProjectPassword = computed(() => (
  authStore.authenticated && (authStore.mode === 'normal' || !authStore.enabled)
))

const configDirSourceLabel = computed(() => {
  const source = String(configDirSource.value || '').toLowerCase()
  if (source === 'env') return '环境变量'
  if (source === 'persisted') return '用户设置'
  if (source === 'default') return '系统默认'
  return source || '-'
})

function initValues() {
  pageModeValue.value = configStore.defaultPageMode
  singlePageBrowsingValue.value = configStore.singlePageBrowsing
  backgroundValue.value = configStore.defaultBackground
  autoDownloadPreviewImportAssets.value = configStore.autoDownloadPreviewImportAssets
  pageSizeValue.value = configStore.listPageSize
  leftRightReadingReversedValue.value = configStore.leftRightReadingReversed
  debugModeValue.value = configStore.debugMode
}

function closeAllDropdowns() {
  activeDropdown.value = ''
}

function toggleDropdown(name, event) {
  if (activeDropdown.value === name) {
    activeDropdown.value = ''
    return
  }
  const rect = event.currentTarget.getBoundingClientRect()
  dropdownPos.value = {
    top: rect.bottom + 4,
    left: rect.right - 140,
    width: rect.width,
  }
  activeDropdown.value = name
}

async function onDropdownSelect(value) {
  const name = activeDropdown.value
  activeDropdown.value = ''
  if (name === 'pageMode') {
    if (pageModeSelection.value === value) return
    await updateReadingMode(value)
  } else if (name === 'pageSize') {
    if (pageSizeValue.value === value) return
    pageSizeValue.value = value
    configStore.setListPageSize(pageSizeValue.value)
  } else if (name === 'background') {
    if (backgroundValue.value === value) return
    backgroundValue.value = value
    updateBackground()
  }
}

function onDocumentClick() {
  activeDropdown.value = ''
}

async function loadSystemConfig() {
  try {
    const response = await configApi.getSystemConfig()
    if (response.code !== 200 || !response.data) {
      return
    }

    systemDataDir.value = response.data.configured_data_dir || ''
    runtimeDataDir.value = response.data.current_runtime_data_dir || ''
    resolvedDataDir.value = response.data.resolved_data_dir || ''
  } catch (error) {
    showFailToast(error?.message || '加载系统配置失败')
  }
}

async function loadConfigDirInfo() {
  try {
    const response = await configApi.getConfigDirInfo()
    if (response.code !== 200 || !response.data) {
      return
    }

    runtimeConfigDir.value = response.data.runtime_config_dir || ''
    selectedConfigDir.value = response.data.selected_config_dir || ''
    defaultConfigDir.value = response.data.default_config_dir || ''
    configDirSource.value = response.data.source || ''
    configDirInput.value = response.data.selected_config_dir || response.data.runtime_config_dir || ''
  } catch (error) {
    showFailToast(error?.message || '加载配置目录信息失败')
  }
}

async function updateReadingMode(value) {
  const reversed = value === 'left_right_reversed'
  pageModeValue.value = value === 'up_down' ? 'up_down' : 'left_right'
  leftRightReadingReversedValue.value = reversed
  configStore.setPageMode(pageModeValue.value)
  configStore.setLeftRightReadingReversed(reversed)
  const ok = await configStore.saveConfigToServer()
  if (!ok) {
    showFailToast('默认翻页模式保存失败')
  }
}

async function updateBackground() {
  configStore.setBackground(backgroundValue.value)
  const ok = await configStore.saveConfigToServer()
  if (!ok) {
    showFailToast('默认背景色保存失败')
  }
}

async function updateSinglePageBrowsing() {
  configStore.setSinglePageBrowsing(singlePageBrowsingValue.value)
  const ok = await configStore.saveConfigToServer()
  if (!ok) {
    showFailToast('单页浏览设置保存失败')
  }
}

function updateFloatingModeSwitch(value) {
  // 纯客户端显示偏好，只写本地配置，不需要同步到服务端
  configStore.setShowFloatingModeSwitch(value)
}

async function updatePreviewImportAssetDownload() {
  configStore.setAutoDownloadPreviewImportAssets(autoDownloadPreviewImportAssets.value)
  const ok = await configStore.saveConfigToServer()
  if (!ok) {
    showFailToast('预览库导入资源下载设置保存失败')
    return
  }
  showSuccessToast('设置已保存')
}

async function updateDebugMode() {
  configStore.updateConfig({ debugMode: debugModeValue.value })
  const ok = await configStore.saveConfigToServer()
  if (!ok) {
    showFailToast('Debug 日志模式保存失败')
    return
  }
  showSuccessToast(debugModeValue.value ? 'Debug 日志已开启' : 'Debug 日志已关闭')
}

async function saveSystemDataDir({ migrateData }) {
  const value = String(systemDataDir.value || '').trim()
  if (!value) {
    showFailToast('请填写 data_dir')
    return
  }

  try {
    await showConfirmDialog({
      title: migrateData ? '确认迁移' : '确认仅修改路径',
      message: migrateData
        ? '将直接移动当前 data 目录到新路径，并自动重启后端使配置生效，是否继续？'
        : '将仅修改 data_dir 配置并重启后端，原目录数据不会移动，是否继续？',
      confirmButtonText: '继续',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  savingSystemConfigMode.value = migrateData ? 'migrate' : 'rebind'
  try {
    const response = await configApi.updateSystemConfig({
      data_dir: value,
      migrate_data: Boolean(migrateData),
      restart_now: true,
    })

    if (response.code === 200) {
      showSuccessToast(
        migrateData
          ? 'data 目录已迁移，后端正在重启，请稍后刷新页面'
          : 'data 目录路径已保存，后端正在重启，请稍后刷新页面'
      )
      setTimeout(() => {
        reloadPage()
      }, 2800)
    } else {
      showFailToast(response.msg || '保存失败')
    }
  } catch (error) {
    if (String(error?.message || '').includes('Network Error')) {
      showSuccessToast('配置已提交，后端重启中，请稍后刷新页面')
      setTimeout(() => {
        reloadPage()
      }, 2800)
      return
    }
    showFailToast(error?.message || '保存失败')
  } finally {
    savingSystemConfigMode.value = ''
  }
}

function saveSystemDataDirWithMigration() {
  return saveSystemDataDir({ migrateData: true })
}

function saveSystemDataDirWithoutMigration() {
  return saveSystemDataDir({ migrateData: false })
}

async function saveConfigDir() {
  const value = String(configDirInput.value || '').trim()
  if (!value) {
    showFailToast('请填写 config_dir')
    return
  }

  try {
    await showConfirmDialog({
      title: '确认修改配置目录',
      message: '将迁移 server_config.json 和 third_party_config.json 到新目录，并重启后端使其生效，是否继续？',
      confirmButtonText: '继续',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  savingConfigDir.value = true
  try {
    const response = await configApi.updateConfigDir({
      config_dir: value,
      migrate_configs: true,
      restart_now: true,
    })

    if (response.code === 200) {
      showSuccessToast('配置目录已保存，后端正在重启，请稍后刷新页面')
      setTimeout(() => {
        reloadPage()
      }, 2800)
    } else {
      showFailToast(response.msg || '保存失败')
    }
  } catch (error) {
    if (String(error?.message || '').includes('Network Error')) {
      showSuccessToast('配置目录已提交，后端重启中，请稍后刷新页面')
      setTimeout(() => {
        reloadPage()
      }, 2800)
      return
    }
    showFailToast(error?.message || '保存失败')
  } finally {
    savingConfigDir.value = false
  }
}

async function saveProjectPassword() {
  if (!canChangeProjectPassword.value) {
    showFailToast('请先进入正常空间')
    return
  }
  const password = String(projectPassword.value || '').trim()
  const confirm = String(projectPasswordConfirm.value || '').trim()
  if (!password) {
    showFailToast('请输入新密码')
    return
  }
  if (password !== confirm) {
    showFailToast('两次输入的密码不一致')
    return
  }

  savingProjectPassword.value = true
  try {
    const response = await authStore.changePassword(password)
    if (response?.code !== 200) {
      showFailToast(response?.msg || '密码保存失败')
      return
    }
    projectPassword.value = ''
    projectPasswordConfirm.value = ''
    showSuccessToast('项目密码已更新，请重启应用以启用双空间')
  } catch (error) {
    showFailToast(error?.message || '密码保存失败')
  } finally {
    savingProjectPassword.value = false
  }
}

async function confirmReset() {
  try {
    await showConfirmDialog({
      title: '重置设置',
      message: '确定要将所有阅读设置恢复为默认值吗？',
    })
  } catch {
    return
  }

  await configStore.resetConfig()
  initValues()
  showSuccessToast('已重置为默认设置')
}

async function organizeDatabase() {
  try {
    await showConfirmDialog({
      title: '整理数据库',
      message: '将补全缺失封面并回写本地实际页数，是否继续？',
    })
  } catch {
    return
  }

  try {
    const response = await comicApi.organizeDatabase()
    const rewritten = response?.data?.home?.rewritten_total_pages ?? 0
    const downloaded = (response?.data?.home?.updated_cover_paths ?? 0) + (response?.data?.recommendation?.updated_cover_paths ?? 0)
    showSuccessToast(`整理完成：补全封面 ${downloaded}，回写页数 ${rewritten}`)
  } catch (error) {
    showFailToast(error?.message || '数据库整理失败')
  }
}

onMounted(async () => {
  try {
    await authStore.checkStatus()
  } catch {
    // The router already handles unavailable startup status; keep settings usable when it recovers.
  }
  await configStore.loadConfigFromServer()
  initValues()
  // 语义检索只在桌面端出现；先拿到运行时能力再决定是否渲染该分区
  try {
    await runtimeStore.fetchRuntime()
  } catch {
    // 读取失败按桌面端处理：后端若确实不支持会在接口层拒绝
  }
  await Promise.all([
    loadSystemConfig(),
    loadConfigDirInfo(),
    loadSemanticState(),
    loadVisionState(),
    loadVisionProviders(),
    loadVisionMissing(),
    loadVisionBatch(),
  ])
  document.addEventListener('click', onDocumentClick)
})

onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick)
  stopVisionBatchPolling()
})
</script>

<style scoped>
.system-config {
  width: min(100%, 1080px);
  min-height: 95vh;
  min-height: 95dvh;
  margin: 0 auto;
  background: transparent;
  padding: 0 var(--page-gutter) calc(28px + env(safe-area-inset-bottom, 0px));
}

.settings-section {
  margin: 0 0 22px;
}

.settings-section--compact {
  margin-bottom: 24px;
}

.settings-section--advanced {
  margin-top: 28px;
}

.section-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
  margin: 0 4px 10px;
}

.section-heading h2 {
  margin: 3px 0 0;
  color: var(--text-strong);
  font-size: 18px;
  line-height: 1.2;
  letter-spacing: -0.02em;
}

.section-kicker {
  display: block;
  color: var(--brand-600);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.section-note {
  padding-bottom: 2px;
  color: var(--text-tertiary);
  font-size: 12px;
  white-space: nowrap;
}

.config-group {
  margin: 0;
  overflow: hidden;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.config-group :deep(.van-cell),
.config-group :deep(.van-field) {
  background: transparent;
}

.settings-card :deep(.van-cell) {
  min-height: 58px;
  padding: 12px 16px;
}

.settings-card :deep(.van-cell__title) {
  min-width: 0;
}

.settings-card :deep(.van-cell__value) {
  flex: 0 0 auto;
}

.settings-card :deep(.van-cell__label) {
  max-width: 700px;
  margin-top: 4px;
  color: var(--text-tertiary);
  line-height: 1.5;
}

.semantic-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 16px 16px;
}

.semantic-line {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding: 7px 0;
  border-top: 1px solid var(--border-soft, rgba(0, 0, 0, 0.06));
  color: var(--text-tertiary);
  font-size: 13px;
}

.semantic-line strong {
  color: var(--text-strong);
  font-size: 13px;
  font-weight: 500;
  text-align: right;
  word-break: break-word;
}

.semantic-note {
  margin: 2px 0 6px;
  color: var(--text-tertiary);
  font-size: 12.5px;
  line-height: 1.6;
}

.vision-drafts {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px 16px 16px;
}

.vision-batch {
  padding: 4px 16px 12px;
}

.vision-batch-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-strong);
  font-size: 13.5px;
}

.vision-batch-head span {
  color: var(--text-tertiary);
  font-size: 12px;
}

.vision-batch-bar {
  height: 4px;
  margin: 8px 0 10px;
  border-radius: 999px;
  background: var(--border-soft, rgba(0, 0, 0, 0.08));
  overflow: hidden;
}

.vision-batch-bar i {
  display: block;
  height: 100%;
  background: var(--brand-600, #8a6f52);
  transition: width 0.3s ease;
}

.vision-batch-actions {
  display: flex;
  gap: 8px;
}

.vision-failures {
  padding: 4px 16px 12px;
}

.vision-failure {
  margin-top: 10px;
  padding: 12px 14px;
  border: 1px solid rgba(180, 84, 63, 0.24);
  border-radius: 14px;
  background: rgba(180, 84, 63, 0.04);
}

.vision-failure-error {
  margin: 0 0 10px;
  color: #b4543f;
  font-size: 12.5px;
  line-height: 1.6;
  word-break: break-word;
}

.vision-field {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
}

.vision-field-label {
  flex: 0 0 auto;
  color: var(--text-strong);
  font-size: 14px;
}

.vision-select {
  flex: 1;
  min-width: 0;
  padding: 7px 10px;
  border: 1px solid var(--border-soft, rgba(0, 0, 0, 0.1));
  border-radius: 10px;
  background: var(--surface-muted, rgba(0, 0, 0, 0.02));
  color: var(--text-strong);
  font-size: 13px;
}

.vision-provider-note {
  margin: 0 16px 10px;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.6;
}

.vision-endpoint {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 16px;
  color: var(--text-tertiary);
  font-size: 12.5px;
}

.vision-endpoint code {
  color: var(--text-strong);
  font-size: 12px;
  word-break: break-all;
  text-align: right;
}

.vision-context {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px 6px;
}

.vision-context-copy {
  min-width: 0;
}

.vision-context-path {
  display: block;
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: 11.5px;
  line-height: 1.5;
  word-break: break-all;
}

.vision-draft {
  border: 1px solid var(--border-soft, rgba(0, 0, 0, 0.08));
  border-radius: 14px;
  padding: 12px 14px;
  background: var(--surface-muted, rgba(0, 0, 0, 0.02));
}

.vision-draft-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.vision-draft-head strong {
  color: var(--text-strong);
  font-size: 14px;
  font-weight: 500;
}

.vision-draft-meta {
  color: var(--text-tertiary);
  font-size: 12px;
}

.vision-draft-text {
  margin: 0 0 6px;
  color: var(--text-secondary, var(--text-strong));
  font-size: 13px;
  line-height: 1.65;
}

.vision-draft-text.secondary,
.vision-draft-tags {
  color: var(--text-tertiary);
  font-size: 12.5px;
  line-height: 1.6;
}

.vision-draft-tags {
  margin: 0 0 10px;
}

.vision-draft-actions {
  display: flex;
  gap: 8px;
}

.select-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 68px;
  padding: 12px 16px;
  cursor: pointer;
  position: relative;
  background: transparent;
  transition: background var(--motion-fast) var(--ease-standard);
}

.select-row:hover {
  background: var(--brand-soft, rgba(89, 160, 255, 0.08));
}

.setting-copy {
  display: grid;
  min-width: 0;
  gap: 4px;
}

.select-label {
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.35;
}

.setting-description {
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.45;
}

.select-value {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 4px;
  color: var(--text-secondary);
  font-size: 14px;
  white-space: nowrap;
}

.config-disclosure {
  margin: 0 0 10px;
  overflow: hidden;
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.config-disclosure-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 70px;
  padding: 12px 16px;
  cursor: pointer;
  list-style: none;
  transition: background var(--motion-fast) var(--ease-standard);
}

.config-disclosure-summary::-webkit-details-marker {
  display: none;
}

.config-disclosure-summary:hover {
  background: var(--brand-soft, rgba(89, 160, 255, 0.08));
}

.disclosure-icon {
  display: inline-flex;
  flex: 0 0 34px;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: 1px solid rgba(89, 160, 255, 0.24);
  border-radius: 11px;
  color: var(--brand-600);
  background: var(--brand-soft, rgba(89, 160, 255, 0.1));
}

.disclosure-copy {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 4px;
}

.disclosure-copy strong {
  overflow: hidden;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.disclosure-copy small {
  overflow: hidden;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.disclosure-chevron {
  flex: 0 0 auto;
  color: var(--text-tertiary);
  transition: transform var(--motion-base) var(--ease-standard);
}

details[open] .disclosure-chevron {
  transform: rotate(90deg);
  color: var(--brand-600);
}

.disclosure-body {
  border-top: 1px solid var(--border-soft);
  padding: 4px 0 2px;
}

.disclosure-note {
  margin: 10px 16px 4px;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.6;
}

.disclosure-body :deep(.van-field) {
  background: transparent;
}

.path-summary-grid {
  display: grid;
  gap: 10px;
  padding: 10px 16px 6px;
}

.path-summary-card {
  display: grid;
  gap: 6px;
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  background: var(--surface-1);
}

.path-summary-card.emphasis {
  border-color: rgba(47, 116, 255, 0.3);
  background: rgba(89, 160, 255, 0.08);
}

.path-summary-label {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.path-summary-value {
  overflow-wrap: anywhere;
  color: var(--text-primary);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.path-summary-meta {
  color: var(--text-tertiary);
  font-size: 12px;
}

.inline-actions {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
  padding: 10px 16px 16px;
}

.secondary-action {
  margin-top: 0;
}

.inline-actions.single {
  grid-template-columns: 1fr;
}

.mmmtttt-config {
  padding: 16px;
  color: var(--text-tertiary);
  font-size: 12px;
  text-align: center;
}

.action-area {
  padding: 16px 0 10px;
}

.settings-mode-switch {
  transform: scale(0.78);
  transform-origin: right center;
}

@media (min-width: 1024px) {
  .system-config {
    padding-inline: 24px;
  }
}

@media (max-width: 767px) {
  .system-config {
    padding-inline: 10px;
  }

  .section-heading {
    margin-inline: 2px;
  }

  .section-heading h2 {
    font-size: 17px;
  }

  .section-note {
    font-size: 11px;
  }

  .config-group,
  .config-disclosure {
    border-radius: 16px;
  }

  .config-disclosure-summary {
    min-height: 66px;
    padding-inline: 13px;
  }

  .disclosure-copy small {
    max-width: calc(100vw - 112px);
  }

  .select-row {
    min-height: 64px;
    padding-inline: 14px;
  }

  .select-value {
    font-size: 13px;
  }
}
</style>

<style>
.select-dropdown-overlay {
  position: fixed;
  z-index: 3000;
  background: var(--popup-bg, #fff);
  border: 1px solid var(--border-soft, rgba(0, 0, 0, 0.08));
  border-radius: 14px;
  box-shadow: var(--shadow-md, 0 8px 24px rgba(0, 0, 0, 0.15));
  overflow: hidden;
  backdrop-filter: blur(12px);
}

.select-dropdown-overlay .select-option {
  padding: 10px 16px;
  font-size: 14px;
  color: var(--text-primary, #333);
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}

.select-dropdown-overlay .select-option:hover {
  background: rgba(47, 116, 255, 0.08);
}

.select-dropdown-overlay .select-option.active {
  color: var(--brand-600, #1989fa);
  font-weight: 600;
  background: rgba(89, 160, 255, 0.12);
}
</style>

