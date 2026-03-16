import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import { useConfigStore } from '@/stores'
import Vant, { Lazyload } from 'vant'
import 'vant/lib/index.css'
import './style.css'

const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)

const app = createApp(App)
app.use(router)
app.use(pinia)
const configStore = useConfigStore(pinia)
configStore.applyAppTheme(configStore.defaultBackground)
app.use(Vant)
app.use(Lazyload)
app.mount('#app')
