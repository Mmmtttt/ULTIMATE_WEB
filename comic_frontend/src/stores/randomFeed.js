import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { feedApi } from '@/api/feed'

function normalizeMode(mode) {
  return mode === 'video' ? 'video' : 'comic'
}

const EMPTY_STATE = () => ({
  sessionId: '',
  items: [],
  loading: false,
  loadingMore: false,
  ready: false,
  error: ''
})

export const useRandomFeedStore = defineStore('randomFeed', () => {
  const comicState = ref(EMPTY_STATE())
  const videoState = ref(EMPTY_STATE())

  const stateByMode = computed(() => ({
    comic: comicState.value,
    video: videoState.value
  }))

  function getState(mode) {
    const key = normalizeMode(mode)
    return key === 'video' ? videoState.value : comicState.value
  }

  function patchState(mode, patch) {
    const key = normalizeMode(mode)
    const target = key === 'video' ? videoState : comicState
    target.value = {
      ...target.value,
      ...patch
    }
  }

  function resetModeState(mode) {
    const key = normalizeMode(mode)
    if (key === 'video') {
      videoState.value = EMPTY_STATE()
    } else {
      comicState.value = EMPTY_STATE()
    }
  }

  async function ensureSession(mode, { forceNew = false } = {}) {
    const key = normalizeMode(mode)
    const current = getState(key)
    if (current.sessionId && !forceNew) {
      return current.sessionId
    }

    patchState(key, { loading: true, error: '' })
    try {
      const response = await feedApi.createSession(key)
      if (response.code !== 200 || !response.data?.session_id) {
        throw new Error(response.msg || '创建随机流会话失败')
      }

      patchState(key, {
        sessionId: response.data.session_id,
        items: [],
        ready: true,
        loading: false,
        loadingMore: false,
        error: ''
      })
      return response.data.session_id
    } catch (error) {
      patchState(key, {
        loading: false,
        loadingMore: false,
        ready: false,
        error: error?.message || '创建随机流会话失败'
      })
      throw error
    }
  }

  async function refreshSequence(mode) {
    const key = normalizeMode(mode)
    const current = getState(key)

    patchState(key, { loading: true, error: '' })
    try {
      const response = await feedApi.refreshSession(current.sessionId, key)
      if (response.code !== 200 || !response.data?.session_id) {
        throw new Error(response.msg || '刷新随机序列失败')
      }

      patchState(key, {
        sessionId: response.data.session_id,
        items: [],
        ready: true,
        loading: false,
        loadingMore: false,
        error: ''
      })
      return response.data.session_id
    } catch (error) {
      patchState(key, {
        loading: false,
        loadingMore: false,
        error: error?.message || '刷新随机序列失败'
      })
      throw error
    }
  }

  async function loadMore(mode, limit = 16) {
    const key = normalizeMode(mode)
    const current = getState(key)
    if (current.loadingMore) {
      return current.items
    }

    let sessionId = current.sessionId
    if (!sessionId) {
      sessionId = await ensureSession(key)
    }

    patchState(key, { loadingMore: true, error: '' })
    try {
      const response = await feedApi.getItems(sessionId, limit)
      if (response.code !== 200) {
        throw new Error(response.msg || '加载随机流失败')
      }
      const newItems = Array.isArray(response.data?.items) ? response.data.items : []
      patchState(key, {
        items: current.items.concat(newItems),
        loadingMore: false,
        ready: true
      })
      return getState(key).items
    } catch (error) {
      patchState(key, {
        loadingMore: false,
        error: error?.message || '加载随机流失败'
      })
      throw error
    }
  }

  async function bootstrapSessions() {
    await Promise.all([
      ensureSession('comic', { forceNew: true }),
      ensureSession('video', { forceNew: true })
    ])
  }

  function getItems(mode) {
    return getState(mode).items
  }

  return {
    comicState,
    videoState,
    stateByMode,
    getState,
    getItems,
    resetModeState,
    ensureSession,
    refreshSequence,
    loadMore,
    bootstrapSessions
  }
})

