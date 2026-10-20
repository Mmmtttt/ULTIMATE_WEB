<template>
  <article class="task-card" :class="[task.status, { active: !history }]">
    <div class="task-header">
      <div class="task-heading">
        <span class="task-title">{{ task.name || '未知任务' }}</span>
        <div class="task-subtitle">
          <span class="engine-tag">{{ task.engine_name || '下载引擎' }}</span>
          <span v-if="!history" class="task-status-text">{{ store.progressMetaText(task) }}</span>
          <span v-else class="task-gid">{{ task.gid }}</span>
        </div>
      </div>
      <div class="task-header-right">
        <van-tag :color="store.getStatusColor(task.status)">
          {{ store.getStatusText(task.status) }}
        </van-tag>
        <div class="task-actions">
          <button
            v-if="!history && task.status === 'paused' && store.taskSupports(task, 'resume')"
            class="icon-btn"
            :disabled="store.taskActionGid === task.gid"
            title="继续下载"
            @click="store.handleResume(task)"
          >
            <van-icon name="play-circle-o" size="20" />
          </button>
          <button
            v-else-if="!history && task.status !== 'paused' && store.taskSupports(task, 'pause')"
            class="icon-btn"
            :disabled="store.taskActionGid === task.gid"
            title="暂停下载"
            @click="store.handlePause(task)"
          >
            <van-icon name="pause-circle-o" size="20" />
          </button>
          <button
            v-if="store.taskSupports(task, 'remove')"
            class="icon-btn danger"
            :disabled="store.taskActionGid === task.gid"
            :title="history ? '删除记录' : '删除任务'"
            @click="store.handleRemove(task)"
          >
            <van-icon name="delete-o" size="20" />
          </button>
        </div>
      </div>
    </div>

    <div v-if="!history" class="progress-section">
      <van-progress
        :percentage="Math.round(Number(task.progress || 0) * 100)"
        :stroke-width="8"
        :color="store.getStatusColor(task.status)"
      />
      <div class="progress-speed">
        <span v-if="task.upload_speed > 0">↑ {{ store.formatSpeed(task.upload_speed) }}</span>
        <span>{{ store.formatBytes(task.completed_length) }} / {{ store.formatBytes(task.total_length) }}</span>
      </div>
    </div>

    <template v-else>
      <div class="task-meta">
        <span>{{ store.formatBytes(task.total_length) }}</span>
        <span v-if="task.dir">{{ task.dir }}</span>
      </div>
      <div v-if="task.error_message" class="error-message">
        <van-icon name="warning-o" />
        <span>{{ task.error_message }}</span>
      </div>
    </template>

    <div v-if="store.taskCapabilityNote(task)" class="task-capability-note">
      {{ store.taskCapabilityNote(task) }}
    </div>
  </article>
</template>

<script setup>
import { useDownloadTaskStore } from '@/stores/downloadTask'

defineProps({
  task: { type: Object, required: true },
  history: { type: Boolean, default: false }
})

const store = useDownloadTaskStore()
</script>

<style scoped>
.task-card {
  padding: 16px;
  border-radius: 16px;
  background: var(--surface-2);
  border: 1px solid var(--border-soft);
  box-shadow: 0 10px 22px rgba(12, 22, 37, 0.1);
}

.task-card.active {
  border-color: rgba(47, 116, 255, 0.24);
}

.task-card.complete {
  border-color: rgba(7, 193, 96, 0.2);
}

.task-card.error {
  border-color: rgba(238, 10, 36, 0.18);
}

.task-card.removed {
  border-color: rgba(150, 151, 153, 0.2);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.task-header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.task-heading {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.task-subtitle {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.engine-tag {
  flex-shrink: 0;
  padding: 1px 8px;
  border-radius: 999px;
  background: rgba(47, 116, 255, 0.12);
  color: #2f74ff;
  font-size: 11px;
  font-weight: 500;
}

.task-status-text {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-strong);
  word-break: break-word;
}

.task-gid {
  font-size: 12px;
  color: var(--text-tertiary);
  font-family: monospace;
  word-break: break-all;
}

.task-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-secondary);
}

.progress-section {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border-soft);
}

.progress-speed {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.task-capability-note {
  margin-top: 10px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-tertiary);
}

.task-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border-radius: 50%;
  border: 1px solid var(--border-soft);
  background: var(--surface-3, var(--surface-2));
  color: var(--text-secondary);
  cursor: pointer;
}

.icon-btn.danger {
  color: #ee0a24;
}

.icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.error-message {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  font-size: 12px;
  line-height: 1.5;
  color: #ee0a24;
}
</style>
