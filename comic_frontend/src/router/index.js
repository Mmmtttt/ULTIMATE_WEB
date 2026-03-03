import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/Home.vue')
  },
  {
    path: '/video-home',
    name: 'VideoHome',
    component: () => import('../views/VideoHome.vue')
  },
  {
    path: '/recommendation',
    name: 'Recommendation',
    component: () => import('../views/Recommendation.vue')
  },
  {
    path: '/recommendation/:id',
    name: 'RecommendationDetail',
    component: () => import('../views/RecommendationDetail.vue')
  },
  {
    path: '/recommendation-reader/:id',
    name: 'RecommendationReader',
    component: () => import('../views/RecommendationReader.vue')
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
    path: '/video/:id',
    name: 'VideoDetail',
    component: () => import('../views/VideoDetail.vue')
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
    path: '/tag/:id',
    name: 'TagDetail',
    component: () => import('../views/TagDetail.vue')
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
  },
  {
    path: '/trash',
    name: 'Trash',
    component: () => import('../views/Trash.vue')
  },
  {
    path: '/import-tasks',
    name: 'ImportTasks',
    component: () => import('../views/ImportTasks.vue')
  },
  {
    path: '/authors',
    name: 'AuthorSubscription',
    component: () => import('../views/AuthorSubscription.vue')
  },
  {
    path: '/actors',
    name: 'ActorSubscription',
    component: () => import('../views/ActorSubscription.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
