import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import { useAppUpdateStore, useConfigStore, useRandomFeedStore } from '@/stores'
import Vant, { Lazyload } from 'vant'
import 'vant/lib/index.css'
import './style.css'

const ARCHIVE_INTENT_SESSION_KEY = 'ultimate_android_open_archive_path'

function normalizeIncomingArchivePath(raw) {
  const text = String(raw || '').trim()
  return text || ''
}

function routeToLocalImportWithArchivePath(rawPath) {
  const sourcePath = normalizeIncomingArchivePath(rawPath)
  if (!sourcePath || typeof window === 'undefined') return

  try {
    window.sessionStorage.setItem(ARCHIVE_INTENT_SESSION_KEY, sourcePath)
  } catch (_error) {
    // ignore storage errors
  }

  const query = {
    source_path: sourcePath,
    source_mode: 'path',
    _intent_ts: String(Date.now())
  }
  const current = router.currentRoute.value
  if (current?.path === '/comic-local-import') {
    void router.replace({
      path: '/comic-local-import',
      query: {
        ...(current.query || {}),
        ...query
      }
    }).catch(() => {})
    return
  }
  void router.push({ path: '/comic-local-import', query }).catch(() => {})
}

if (typeof window !== 'undefined') {
  window.addEventListener('ultimateArchiveOpen', (event) => {
    const archivePath = normalizeIncomingArchivePath(event?.detail?.path)
    if (!archivePath) return
    routeToLocalImportWithArchivePath(archivePath)
  })

  try {
    const bootPath = normalizeIncomingArchivePath(window.sessionStorage.getItem(ARCHIVE_INTENT_SESSION_KEY))
    if (bootPath) {
      routeToLocalImportWithArchivePath(bootPath)
    }
  } catch (_error) {
    // ignore storage errors
  }
}

const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)

const app = createApp(App)
app.use(router)
app.use(pinia)
const configStore = useConfigStore(pinia)
const randomFeedStore = useRandomFeedStore(pinia)
const appUpdateStore = useAppUpdateStore(pinia)
configStore.applyAppTheme(configStore.defaultBackground)
randomFeedStore.bootstrapSessions().catch((error) => {
  console.warn('[RandomFeed] bootstrap failed:', error)
})
app.use(Vant)
app.use(Lazyload)
app.mount('#app')

appUpdateStore.checkForUpdates({ source: 'startup', showPrompt: true }).catch((error) => {
  console.warn('[Update] startup check failed:', error)
})
