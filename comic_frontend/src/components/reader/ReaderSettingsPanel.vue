<template>
  <van-popup v-model:show="open" position="bottom" round class="reader-settings-panel">
    <div class="reader-settings-header">
      <div>
        <span class="reader-settings-kicker">READER CONTROL</span>
        <h3>阅读设置</h3>
      </div>
      <van-icon name="cross" size="20" @click="open = false" />
    </div>

    <div class="reader-settings-body">
      <div class="reader-setting-row">
        <div>
          <strong>双页模式</strong>
          <small>左右翻页时并排显示两页</small>
        </div>
        <van-switch
          :model-value="configStore.doublePageMode"
          data-testid="reader-double-page"
          @update:model-value="set('doublePageMode', $event)"
        />
      </div>

      <div v-if="configStore.doublePageMode" class="reader-setting-row">
        <div>
          <strong>双页首屏留白</strong>
          <small>从第一页开始时保留阅读方向的对齐空位</small>
        </div>
        <van-switch
          :model-value="configStore.doublePageLeadingBlank"
          data-testid="reader-double-page-leading-blank"
          @update:model-value="set('doublePageLeadingBlank', $event)"
        />
      </div>

      <div class="reader-setting-row">
        <div>
          <strong>条漫点击翻页</strong>
          <small>上下阅读时允许点击左右区域切换页面</small>
        </div>
        <van-switch
          :model-value="configStore.tapPageTurnInWebtoon"
          data-testid="reader-webtoon-tap-turn"
          @update:model-value="set('tapPageTurnInWebtoon', $event)"
        />
      </div>

      <div class="reader-setting-row">
        <div>
          <strong>自动阅读</strong>
          <small>按设定速度自动翻页，到末页自动停止</small>
        </div>
        <van-switch
          :model-value="autoReadActive"
          data-testid="reader-auto-read"
          @update:model-value="$emit('toggle-auto-read')"
        />
      </div>

      <div class="reader-setting-row reader-setting-row--column">
        <div class="reader-setting-label-line">
          <div>
            <strong>自动阅读速度</strong>
            <small>{{ formatInterval(configStore.autoReadInterval) }}</small>
          </div>
        </div>
        <van-slider
          :model-value="speedSlider"
          :min="1"
          :max="6"
          :step="1"
          data-testid="reader-auto-read-speed"
          @update:model-value="updateSpeed"
        />
      </div>

      <div class="reader-setting-row reader-setting-row--column">
        <div class="reader-setting-label-line">
          <div>
            <strong>点击翻页区域</strong>
            <small>全屏点击显示菜单，也可固定左右区域翻页</small>
          </div>
        </div>
        <div class="reader-choice-grid" data-testid="reader-tap-mode">
          <button
            v-for="item in tapModes"
            :key="item.value"
            type="button"
            :class="{ active: configStore.tapPageTurnMode === item.value }"
            @click="set('tapPageTurnMode', item.value)"
          >{{ item.label }}</button>
        </div>
      </div>

      <div class="reader-setting-row">
        <div>
          <strong>双击动作</strong>
          <small>放大图片或打开控制栏</small>
        </div>
        <div class="reader-segmented-control">
          <button type="button" :class="{ active: configStore.doubleTapAction === 'zoom' }" @click="set('doubleTapAction', 'zoom')">放大</button>
          <button type="button" :class="{ active: configStore.doubleTapAction === 'menu' }" @click="set('doubleTapAction', 'menu')">菜单</button>
        </div>
      </div>

      <div class="reader-setting-row reader-setting-row--column">
        <div class="reader-setting-label-line">
          <div>
            <strong>阅读滤镜</strong>
            <small>{{ Math.round(configStore.readFilterOpacity * 100) }}% 暗化</small>
          </div>
        </div>
        <van-slider
          :model-value="filterSlider"
          :min="0"
          :max="80"
          :step="5"
          data-testid="reader-filter"
          @update:model-value="set('readFilterOpacity', Number($event) / 100)"
        />
      </div>

      <div class="reader-setting-row reader-setting-row--column">
        <div class="reader-setting-label-line">
          <div>
            <strong>两侧留白</strong>
            <small>{{ configStore.readerSidePadding }}%</small>
          </div>
        </div>
        <van-slider
          :model-value="configStore.readerSidePadding"
          :min="0"
          :max="30"
          :step="5"
          data-testid="reader-side-padding"
          @update:model-value="set('readerSidePadding', $event)"
        />
      </div>

      <div class="reader-setting-row">
        <div>
          <strong>关闭翻页动画</strong>
          <small>适合追求即时响应或电子墨水屏</small>
        </div>
        <van-switch
          :model-value="configStore.noReaderAnimation"
          data-testid="reader-no-animation"
          @update:model-value="set('noReaderAnimation', $event)"
        />
      </div>
    </div>
  </van-popup>
</template>

<script setup>
import { computed } from 'vue'
import { useConfigStore } from '@/stores'

const props = defineProps({
  show: { type: Boolean, default: false },
  autoReadActive: { type: Boolean, default: false }
})

const emit = defineEmits(['update:show', 'toggle-auto-read'])
const configStore = useConfigStore()
const open = computed({
  get: () => props.show,
  set: (value) => emit('update:show', value)
})

const tapModes = [
  { label: '菜单', value: 'full' },
  { label: '左侧上一页', value: 'left' },
  { label: '右侧下一页', value: 'right' }
]
const speedValues = [10000, 8000, 6000, 5000, 3000, 1500]
const speedSlider = computed(() => {
  const index = speedValues.indexOf(Number(configStore.autoReadInterval))
  return index >= 0 ? index + 1 : 4
})
const filterSlider = computed(() => Math.round(Number(configStore.readFilterOpacity || 0) * 100))

const set = (name, value) => configStore.setReaderPreference(name, value)
const updateSpeed = (value) => set('autoReadInterval', speedValues[Math.max(0, Number(value) - 1)] || 5000)
const formatInterval = (value) => `${(Number(value) / 1000).toFixed(1)} 秒/页`
</script>

<style scoped>
.reader-settings-panel { max-height: min(82vh, 760px); background: var(--reader-panel-bg, #101827); color: var(--reader-panel-text, #eef4ff); }
.reader-settings-header { display: flex; align-items: center; justify-content: space-between; padding: 20px 22px 14px; border-bottom: 1px solid rgba(255,255,255,.08); }
.reader-settings-kicker { color: #79a9ff; font-size: 10px; letter-spacing: .16em; font-weight: 700; }
.reader-settings-header h3 { margin: 4px 0 0; font-size: 20px; }
.reader-settings-body { overflow: auto; padding: 4px 22px 24px; }
.reader-setting-row { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 16px 0; border-bottom: 1px solid rgba(255,255,255,.07); }
.reader-setting-row--column { display: block; }
.reader-setting-row strong { display: block; font-size: 14px; }
.reader-setting-row small { display: block; margin-top: 4px; color: rgba(230,239,255,.58); font-size: 12px; line-height: 1.4; }
.reader-setting-label-line { display: flex; justify-content: space-between; margin-bottom: 14px; }
.reader-choice-grid, .reader-segmented-control { display: flex; gap: 8px; flex-wrap: wrap; }
.reader-choice-grid button, .reader-segmented-control button { border: 1px solid rgba(125,166,255,.28); color: #c8d9ff; background: rgba(91,132,218,.1); border-radius: 10px; padding: 8px 11px; font-size: 12px; }
.reader-choice-grid button.active, .reader-segmented-control button.active { background: #4e88f5; border-color: #4e88f5; color: white; }
.van-slider { margin: 0 3px; }
@media (min-width: 700px) { .reader-settings-panel { width: min(560px, 100vw); margin: 0 auto; } }
</style>
