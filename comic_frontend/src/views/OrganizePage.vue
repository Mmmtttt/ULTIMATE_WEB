<template>
  <div class="organize-page desktop-page-shell">
    <van-nav-bar
      title="数据库整理"
      left-arrow
      @click-left="$router.back()"
    >
      <template #right>
        <van-button
          size="small"
          plain
          :loading="loadingOrganizeOptions"
          @click="loadOrganizeOptions"
        >
          刷新
        </van-button>
      </template>
    </van-nav-bar>

    <div class="organize-content">
      <van-skeleton v-if="loadingOrganizeOptions && organizeActions.length === 0" title :row="6" />

      <template v-else-if="organizeActions.length > 0">
        <section class="organize-section">
          <van-cell-group inset>
            <van-cell
              v-for="(action, index) in organizeActions"
              :key="index"
              :title="action.name"
              :label="action.subname"
              is-link
              :disabled="action.disabled"
              @click="handleOrganizeAction(action)"
            />
          </van-cell-group>
        </section>
      </template>

      <van-empty v-else description="暂无可用整理功能" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useModeStore } from '@/stores'
import { organizeApi } from '@/api'
import { closeToast, showFailToast, showConfirmDialog, showLoadingToast } from 'vant'

const modeStore = useModeStore()

const isVideoMode = computed(() => modeStore.isVideoMode)
const organizeModeKey = computed(() => (isVideoMode.value ? 'video' : 'comic'))
const organizeActions = ref([])
const runningOrganizeAction = ref(false)
const loadingOrganizeOptions = ref(false)

function mapOrganizeActions(rawOptions) {
  if (!Array.isArray(rawOptions)) {
    return []
  }
  return rawOptions.map((item) => ({
    ...item,
    name: item?.name || item?.action || '未知功能',
    subname: item?.description || '',
    disabled: item?.implemented === false,
  }))
}

function buildOrganizeResultMessage(action, payload) {
  if (payload?.summary) {
    return payload.summary
  }
  if (action === 'repair_cover') {
    const rewritten = Number(payload?.home?.rewritten_total_pages || 0)
    const repaired = Number(payload?.home?.updated_cover_paths || 0) + Number(payload?.recommendation?.updated_cover_paths || 0)
    return `修复封面完成：修复封面 ${repaired}，回写页数 ${rewritten}`
  }
  if (action === 'deduplicate_by_title' || action === 'deduplicate_by_code') {
    const home = Number(payload?.home?.moved_to_trash || 0)
    const recommendation = Number(payload?.recommendation?.moved_to_trash || 0)
    return `查重完成：本地库 ${home} 条，预览库 ${recommendation} 条`
  }
  if (action === 'enrich_local_metadata') {
    const updated = Number(payload?.updated_records || 0)
    const noMatch = Number(payload?.skipped_no_match || 0)
    return `LOCAL 补全完成：成功 ${updated}，无匹配 ${noMatch}`
  }
  return '数据库整理已完成'
}

function buildOrganizeResultDetail(action, payload) {
  const summary = buildOrganizeResultMessage(action, payload)
  if (action === 'enrich_local_metadata') {
    const lines = [
      summary,
      `处理候选: ${Number(payload?.processed_candidates || 0)}`,
      `无匹配: ${Number(payload?.skipped_no_match || 0)}`,
      `已补全跳过: ${Number(payload?.skipped_already_enriched || 0)}`
    ]
    const matchedByPlatform = payload?.matched_by_platform
    const entries = matchedByPlatform && typeof matchedByPlatform === 'object'
      ? Object.entries(matchedByPlatform)
      : []
    if (entries.length > 0) {
      entries.forEach(([platform, count]) => {
        lines.push(`${String(platform || '').toUpperCase()}命中: ${Number(count || 0)}`)
      })
    } else {
      const platformOrder = Array.isArray(payload?.search_platform_order)
        ? payload.search_platform_order
        : []
      platformOrder.forEach((platform) => {
        lines.push(`${String(platform || '').toUpperCase()}命中: 0`)
      })
    }
    return lines.join('\n')
  }
  if (action === 'deduplicate_by_title' || action === 'deduplicate_by_code') {
    return [
      summary,
      `本地库移入回收站: ${Number(payload?.home?.moved_to_trash || 0)}`,
      `预览库移入回收站: ${Number(payload?.recommendation?.moved_to_trash || 0)}`
    ].join('\n')
  }
  return summary
}

async function loadOrganizeOptions() {
  if (runningOrganizeAction.value || loadingOrganizeOptions.value) return
  loadingOrganizeOptions.value = true
  try {
    const response = await organizeApi.getOptions(organizeModeKey.value)
    organizeActions.value = mapOrganizeActions(response?.data?.options)
    if (!organizeActions.value.length) {
      showFailToast('当前模式暂无可用整理功能')
    }
  } catch (error) {
    showFailToast(error?.message || '加载数据库整理功能失败')
  } finally {
    loadingOrganizeOptions.value = false
  }
}

async function handleOrganizeAction(selectedAction) {
  if (!selectedAction?.action) return
  if (selectedAction?.implemented === false) {
    showFailToast(selectedAction?.confirm_message || '该功能尚未实现')
    return
  }

  try {
    await showConfirmDialog({
      title: '数据库整理',
      message: selectedAction?.confirm_message || `确定执行「${selectedAction?.name || selectedAction?.action}」吗？`
    })
  } catch {
    return
  }

  runningOrganizeAction.value = true
  showLoadingToast({
    message: `正在执行「${selectedAction?.name || '数据库整理'}」...`,
    forbidClick: true,
    duration: 0
  })
  try {
    const response = await organizeApi.run(organizeModeKey.value, selectedAction.action)
    closeToast()
    const resultText = buildOrganizeResultDetail(selectedAction.action, response?.data || {})
    await showConfirmDialog({
      title: '执行完成',
      message: resultText,
      confirmButtonText: '知道了',
      showCancelButton: false
    })
  } catch (error) {
    closeToast()
    showFailToast(error?.message || '数据库整理失败')
  } finally {
    runningOrganizeAction.value = false
  }
}

onMounted(() => {
  loadOrganizeOptions()
})
</script>

<style scoped>
.organize-page {
  min-height: 95vh;
  background: transparent;
  padding-bottom: 24px;
}

.organize-content {
  padding: 0 12px;
}

.organize-section {
  margin-top: 12px;
}
</style>
