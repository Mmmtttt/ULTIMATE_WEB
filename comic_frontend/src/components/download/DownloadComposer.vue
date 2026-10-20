<template>
  <van-popup
    v-model:show="store.showAddPopup"
    round
    teleport="body"
    :position="popupPosition"
    class="add-popup"
    :class="{ 'add-popup--center': !isMobile }"
  >
    <div class="add-popup-content">
      <div class="add-popup-header">
        <span class="add-popup-title">手动添加下载链接</span>
        <van-icon name="cross" class="add-popup-close" @click="store.showAddPopup = false" />
      </div>
      <div class="add-popup-hint">
        支持磁力链接、HTTP/FTP 直链、BT 种子文件链接，每行一个。
      </div>
      <van-field
        :model-value="store.selectedEngine ? store.selectedEngine.name : '请选择下载引擎'"
        readonly
        is-link
        label="下载平台"
        placeholder="请选择下载引擎"
        @click="store.openEnginePicker"
      />
      <van-field
        v-model="store.manualSubfolder"
        label="子文件夹"
        placeholder="可选，如 ABC-123，留空用根目录"
        clearable
      />
      <van-field
        v-model="store.manualLinks"
        type="textarea"
        rows="6"
        autosize
        maxlength="8000"
        placeholder="每行一个链接&#10;magnet:?xt=urn:btih:...&#10;https://example.com/file.torrent"
      />
      <div class="add-popup-actions">
        <van-button
          block
          type="primary"
          :loading="store.addingLinks"
          :disabled="!store.canAddLinks"
          @click="store.submitManualLinks"
        >
          创建任务
        </van-button>
      </div>
    </div>
    <van-action-sheet
      v-model:show="store.showEnginePicker"
      :actions="store.enginePickerActions"
      cancel-text="取消"
      @select="store.onEngineSelect"
    />
  </van-popup>
</template>

<script setup>
import { computed } from 'vue'
import { useDownloadTaskStore } from '@/stores/downloadTask'
import { useDevice } from '@/composables/useDevice'

const store = useDownloadTaskStore()
const { isMobile } = useDevice()

// 电脑端从屏幕中间弹出，手机端仍从底部弹出
const popupPosition = computed(() => (isMobile.value ? 'bottom' : 'center'))
</script>

<style scoped>
.add-popup-content {
  padding: 16px 16px 20px;
}

/* 居中弹窗需要固定宽度，否则会被内容撑成一条 */
.add-popup--center .add-popup-content {
  width: min(92vw, 440px);
}

.add-popup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.add-popup-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-strong);
}

.add-popup-close {
  color: var(--text-3, var(--text-tertiary));
  cursor: pointer;
}

.add-popup-hint {
  margin-bottom: 10px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-tertiary);
}

.add-popup-actions {
  margin-top: 14px;
}
</style>
