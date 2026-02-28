import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/Home.vue')
  },
  {
    path: '/mine',
    name: 'Mine',
    component: () => import('../views/Mine.vue')
  },
  {
    path: '/comic/:id',
    name: 'ComicDetail',
    component: () => import('../views/ComicDetail.vue')
  },
  {
    path: '/reader/:id',
    name: 'ComicReader',
    component: () => import('../views/ComicReader.vue')
  },
  {
    path: '/tags',
    name: 'TagManage',
    component: () => import('../views/TagManage.vue')
  },
  {
    path: '/lists',
    name: 'ListManage',
    component: () => import('../views/ListManage.vue')
  },
  {
    path: '/list/:id',
    name: 'ListDetail',
    component: () => import('../views/ListDetail.vue')
  },
  {
    path: '/config',
    name: 'SystemConfig',
    component: () => import('../views/SystemConfig.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
