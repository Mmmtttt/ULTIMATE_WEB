import { createRouter, createWebHistory } from 'vue-router'
import { setDocumentTitle } from '@/runtime/browser'
import MainLayout from '@/layouts/MainLayout.vue'
import { useModeStore } from '@/stores/mode'

const routes = [
  {
    path: '/',
    component: MainLayout,
    redirect: '/library',
    children: [
      {
        path: 'library',
        name: 'Library',
        component: () => import('@/views/library/Library.vue'),
        meta: { title: '本地库' }
      },
      {
        path: 'preview',
        name: 'Preview',
        component: () => import('@/views/preview/Preview.vue'),
        meta: { title: '预览库' }
      },
      {
        path: 'subscribe',
        name: 'Subscribe',
        component: () => import('@/views/subscribe/SubscriptionList.vue'),
        meta: { title: '订阅' }
      },
      {
        path: 'mine',
        name: 'Mine',
        component: () => import('@/views/Mine.vue'),
        meta: { title: '我的' }
      }
    ]
  },
  {
    path: '/search',
    name: 'GlobalSearch',
    component: () => import('@/views/search/GlobalSearch.vue'),
    meta: { title: '搜索' }
  },
  {
    path: '/video-tag-search',
    name: 'VideoTagSearch',
    component: () => import('@/views/search/VideoTagSearch.vue'),
    meta: { title: 'JAVDB标签搜索' }
  },
  {
    path: '/creator/:name',
    name: 'CreatorDetail',
    component: () => import('@/views/subscribe/CreatorDetail.vue'),
    meta: { title: '创作者详情' }
  },
  // 保留原有详情页路由，但可能需要适配
  {
    path: '/comic/:id',
    name: 'ComicDetail',
    component: () => import('@/views/ComicDetail.vue')
  },
  {
    path: '/video/:id',
    name: 'VideoDetail',
    component: () => import('@/views/VideoDetail.vue')
  },
  {
    path: '/reader/:id',
    name: 'ComicReader',
    component: () => import('@/views/ComicReader.vue')
  },
  {
    path: '/recommendation/:id',
    name: 'RecommendationDetail',
    component: () => import('@/views/RecommendationDetail.vue')
  },
  {
    path: '/recommendation-reader/:id',
    name: 'RecommendationReader',
    component: () => import('@/views/RecommendationReader.vue')
  },
  {
    path: '/video-recommendation/:id',
    name: 'VideoRecommendationDetail',
    component: () => import('@/views/VideoRecommendationDetail.vue')
  },
  // 管理页面
  {
    path: '/tags',
    name: 'TagManage',
    component: () => import('@/views/TagManage.vue')
  },
  {
    path: '/video-tags',
    name: 'VideoTagManage',
    component: () => import('@/views/VideoTagManage.vue')
  },
  {
    path: '/tag/:id',
    name: 'TagDetail',
    component: () => import('@/views/TagDetail.vue')
  },
  {
    path: '/video-tag/:id',
    name: 'VideoTagDetail',
    component: () => import('@/views/VideoTagDetail.vue')
  },
  {
    path: '/lists',
    name: 'ListManage',
    component: () => import('@/views/ListManage.vue')
  },
  {
    path: '/list/:id',
    name: 'ListDetail',
    component: () => import('@/views/ListDetail.vue')
  },
  {
    path: '/config',
    name: 'SystemConfig',
    component: () => import('@/views/SystemConfig.vue')
  },
  {
    path: '/sync',
    name: 'SyncCenter',
    component: () => import('@/views/SyncCenter.vue'),
    meta: { title: 'Data Sync' }
  },
  {
    path: '/trash',
    name: 'Trash',
    component: () => import('@/views/Trash.vue')
  },
  {
    path: '/import-tasks',
    name: 'ImportTasks',
    component: () => import('@/views/ImportTasks.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫：更新页面标题
router.beforeEach((to, from, next) => {
  if (to.meta.title) {
    setDocumentTitle(`${to.meta.title} - Ultimate`)
  }
  next()
})

export default router
