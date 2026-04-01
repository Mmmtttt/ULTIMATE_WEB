import { computed, ref, unref, watch } from 'vue'
import { useConfigStore } from '@/stores'
import { DEFAULT_CONFIG, STORAGE_KEYS } from '@/utils'
import { getItem, setItem } from '@/utils/storage'

function normalizePageValue(value, fallback = 1) {
  const parsed = Number(value)
  if (Number.isFinite(parsed) && parsed >= 1) {
    return Math.floor(parsed)
  }
  return fallback
}

function resolveStorageKey(keySource) {
  if (typeof keySource === 'function') {
    return String(keySource() || '').trim()
  }
  return String(unref(keySource) || '').trim()
}

function toStorageKey(key) {
  return `${STORAGE_KEYS.PAGINATION_STATE}:${key}`
}

export function usePersistentPage(storageKey, options = {}) {
  const initialPage = normalizePageValue(options.initialPage, 1)
  const currentPage = ref(initialPage)
  const activeStorageKey = ref('')

  function loadPageForKey(key) {
    if (!key) {
      currentPage.value = initialPage
      activeStorageKey.value = ''
      return
    }
    activeStorageKey.value = key
    const saved = getItem(toStorageKey(key), initialPage)
    currentPage.value = normalizePageValue(saved, initialPage)
  }

  watch(
    () => resolveStorageKey(storageKey),
    (key) => loadPageForKey(key),
    { immediate: true }
  )

  watch(currentPage, (page) => {
    if (!activeStorageKey.value) {
      return
    }
    setItem(toStorageKey(activeStorageKey.value), normalizePageValue(page, initialPage))
  })

  function setPage(page) {
    currentPage.value = normalizePageValue(page, 1)
  }

  function goFirst() {
    currentPage.value = 1
  }

  function ensureWithinRange(maxPage) {
    const normalizedMax = normalizePageValue(maxPage, 1)
    if (currentPage.value > normalizedMax) {
      currentPage.value = normalizedMax
    }
    if (currentPage.value < 1) {
      currentPage.value = 1
    }
  }

  return {
    currentPage,
    setPage,
    goFirst,
    ensureWithinRange
  }
}

export function useClientPagination(itemsRef, storageKey, options = {}) {
  const configStore = useConfigStore()
  const pageSize = computed(() => {
    const size = Number(configStore.listPageSize)
    if (Number.isFinite(size) && size > 0) {
      return size
    }
    return DEFAULT_CONFIG.LIST_PAGE_SIZE
  })

  const sourceItems = computed(() => {
    const raw = unref(itemsRef)
    return Array.isArray(raw) ? raw : []
  })

  const totalItems = computed(() => sourceItems.value.length)
  const totalPages = computed(() => {
    return Math.max(1, Math.ceil(totalItems.value / pageSize.value))
  })

  const { currentPage, setPage, goFirst, ensureWithinRange } = usePersistentPage(storageKey, options)

  watch([totalPages, pageSize], ([maxPage]) => {
    ensureWithinRange(maxPage)
  }, { immediate: true })

  const pagedItems = computed(() => {
    if (totalItems.value === 0) {
      return []
    }
    const start = (currentPage.value - 1) * pageSize.value
    const end = start + pageSize.value
    return sourceItems.value.slice(start, end)
  })

  const range = computed(() => {
    if (totalItems.value === 0) {
      return { start: 0, end: 0 }
    }
    const start = (currentPage.value - 1) * pageSize.value + 1
    const end = Math.min(totalItems.value, start + pageSize.value - 1)
    return { start, end }
  })

  return {
    pageSize,
    currentPage,
    totalItems,
    totalPages,
    pagedItems,
    range,
    setPage,
    goFirst,
    ensureWithinRange
  }
}
