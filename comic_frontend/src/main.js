import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import { useAppUpdateStore, useConfigStore, useRandomFeedStore } from '@/stores'
import Vant, { Lazyload } from 'vant'
import 'vant/lib/index.css'
import './style.css'

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
