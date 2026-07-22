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
        path: 'random-feed',
        name: 'RandomFeed',
        component: () => import('@/views/RandomFeed.vue'),
        meta: { title: '随机流' }
      },
      {
        path: 'teledrive-import',
        name: 'TeleDriveImport',
        component: () => import('@/views/TeleDriveImport.vue'),
        meta: { title: 'TeleDrive' }
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
        meta: { title: '管理' }
      },
      // 管理二级页面 —— 保持在主布局内，保持侧边栏 / tabbar
      {
        path: 'tags',
        name: 'TagManage',
        component: () => import('@/views/TagManage.vue'),
        meta: { title: '标签管理' }
      },
      {
        path: 'video-tags',
        name: 'VideoTagManage',
        component: () => import('@/views/VideoTagManage.vue'),
        meta: { title: '视频标签管理' }
      },
      {
        path: 'tag/:id',
        name: 'TagDetail',
        component: () => import('@/views/TagDetail.vue'),
        meta: { title: '标签详情' }
      },
      {
        path: 'video-tag/:id',
        name: 'VideoTagDetail',
        component: () => import('@/views/VideoTagDetail.vue'),
        meta: { title: '视频标签详情' }
      },
      {
        path: 'lists',
        name: 'ListManage',
        component: () => import('@/views/ListManage.vue'),
        meta: { title: '清单管理' }
      },
      {
        path: 'list/:id',
        name: 'ListDetail',
        component: () => import('@/views/ListDetail.vue'),
        meta: { title: '清单详情' }
      },
      {
        path: 'config',
        name: 'SystemConfig',
        component: () => import('@/views/SystemConfig.vue'),
        meta: { title: '系统设置' }
      },
      {
        path: 'config/third-party',
        name: 'ThirdPartyConfig',
        component: () => import('@/views/ThirdPartyConfig.vue'),
        meta: { title: '第三方平台配置' }
      },
      {
        path: 'sync',
        name: 'SyncCenter',
        component: () => import('@/views/SyncCenter.vue'),
        meta: { title: '数据同步' }
      },
      {
        path: 'trash',
        name: 'Trash',
        component: () => import('@/views/Trash.vue'),
        meta: { title: '回收站' }
      },
      {
        path: 'import-tasks',
        name: 'ImportTasks',
        component: () => import('@/views/ImportTasks.vue'),
        meta: { title: '任务中心' }
      },
      {
        path: 'comic-local-import',
        name: 'ComicLocalImport',
        component: () => import('@/views/ComicLocalImport.vue'),
        meta: { title: '本地漫画导入' }
      },
      {
        path: 'video-local-import',
        name: 'VideoLocalImport',
        component: () => import('@/views/VideoLocalImport.vue'),
        meta: { title: '本地视频导入' }
      },
      {
        path: 'storage',
        name: 'StorageManage',
        component: () => import('@/views/StorageManage.vue'),
        meta: { title: '存储管理' }
      },
      {
        path: 'organize',
        name: 'OrganizePage',
        component: () => import('@/views/OrganizePage.vue'),
        meta: { title: '数据库整理' }
      },
      {
        path: 'search',
        name: 'GlobalSearch',
        component: () => import('@/views/search/GlobalSearch.vue'),
        meta: { title: '全网搜索' }
      },
      // 详情 / 阅读器 —— 保持在主布局内
      {
        path: 'comic/:id',
        name: 'ComicDetail',
        component: () => import('@/views/ComicDetail.vue'),
        meta: { title: '漫画详情' }
      },
      {
        path: 'video/:id',
        name: 'VideoDetail',
        component: () => import('@/views/VideoDetail.vue'),
        meta: { title: '视频详情' }
      },
      {
        path: 'reader/:id',
        name: 'ComicReader',
        component: () => import('@/views/ComicReader.vue'),
        meta: { title: '漫画阅读' }
      },
      {
        path: 'recommendation/:id',
        name: 'RecommendationDetail',
        component: () => import('@/views/RecommendationDetail.vue'),
        meta: { title: '推荐详情' }
      },
      {
        path: 'recommendation-reader/:id',
        name: 'RecommendationReader',
        component: () => import('@/views/RecommendationReader.vue'),
        meta: { title: '推荐阅读' }
      },
      {
        path: 'video-recommendation/:id',
        name: 'VideoRecommendationDetail',
        component: () => import('@/views/VideoRecommendationDetail.vue'),
        meta: { title: '视频推荐详情' }
      },
      {
        path: 'creator/:name',
        name: 'CreatorDetail',
        component: () => import('@/views/subscribe/CreatorDetail.vue'),
        meta: { title: '创作者详情' }
      },
      {
        path: 'video-tag-search',
        name: 'VideoTagSearch',
        component: () => import('@/views/search/VideoTagSearch.vue'),
        meta: { title: '平台标签搜索' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 璺敱瀹堝崼锛氭洿鏂伴〉闈㈡爣棰?
router.beforeEach((to, from, next) => {
  if (to.meta.title) {
    setDocumentTitle(`${to.meta.title} - Ultimate`)
  }
  next()
})

export default router
