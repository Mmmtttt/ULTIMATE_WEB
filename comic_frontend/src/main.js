import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import pinia from './store'
import Vant, { Lazyload } from 'vant'
import 'vant/lib/index.css'

const app = createApp(App)
app.use(router)
app.use(pinia)
app.use(Vant)
app.use(Lazyload)
app.mount('#app')
