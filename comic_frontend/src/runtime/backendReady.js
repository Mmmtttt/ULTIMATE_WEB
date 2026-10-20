import { resolveBackendOrigin } from '@/runtime/endpoint'

/**
 * 内嵌后端就绪门（Android 冷启动）。
 *
 * 安卓端由 MainActivity 在后台线程里启动 Chaquopy 后端，WebView 不等它就开始
 * 加载前端；冷启动时认证状态探测会先撞上「端口还没 listen」，被 axios 归类成
 * Network Error，再被全局拦截器弹成用户可见错误。
 *
 * 这里在首次业务请求之前，用 /health 做带退避的轮询，等监听真正就绪再放行。
 * 只有注入了绝对地址的运行时才需要这道门（打包后的安卓端）；开发态、以及由
 * 前端服务器代理解析的桌面端没有可探测的绝对 origin，直接放行，行为不变。
 */

// 前 3 秒密集探测（后端通常在这个区间就绪），之后逐步退避，总预算约 15 秒。
const READY_POLL_SCHEDULE_MS = [
  0, 120, 160, 200, 250, 300, 350, 400, 500, 600, 700, 800,
  1000, 1200, 1500, 1800, 2200, 2600, 3000
]
const GATE_TIMEOUT_MS = 15000
const HEALTH_REQUEST_TIMEOUT_MS = 3000

let readyPromise = null

function resolveHealthUrl() {
  const origin = resolveBackendOrigin()
  if (!origin) return ''
  return `${origin.replace(/\/+$/, '')}/health`
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function probeHealth(url) {
  if (typeof window === 'undefined' || typeof window.fetch !== 'function') return false
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), HEALTH_REQUEST_TIMEOUT_MS)
  try {
    const response = await window.fetch(url, {
      method: 'GET',
      cache: 'no-store',
      credentials: 'omit',
      signal: controller.signal
    })
    return Boolean(response && response.ok)
  } catch (_) {
    return false
  } finally {
    window.clearTimeout(timer)
  }
}

async function runReadinessGate(url) {
  const startedAt = Date.now()
  for (const scheduledDelay of READY_POLL_SCHEDULE_MS) {
    const remaining = GATE_TIMEOUT_MS - (Date.now() - startedAt)
    if (remaining <= 0) break
    // 最后一次等待不超过剩余预算，避免超时后再多等一个退避档位。
    const delayMs = Math.min(scheduledDelay, remaining)
    if (delayMs) await delay(delayMs)
    if (await probeHealth(url)) {
      return { ready: true, skipped: false, waitedMs: Date.now() - startedAt }
    }
  }
  return { ready: false, skipped: false, timedOut: true, waitedMs: Date.now() - startedAt }
}

/** 当前运行时是否需要就绪门（是否注入了绝对后端地址）。 */
export function isBackendGateEnabled() {
  return Boolean(resolveHealthUrl())
}

/**
 * 等待内嵌后端就绪。
 * 成功结果会被缓存，避免每次调用都重探；超时不缓存，登录页重试时还能再探一次。
 */
export function waitForBackendReady() {
  const url = resolveHealthUrl()
  if (!url) {
    return Promise.resolve({ ready: false, skipped: true, waitedMs: 0 })
  }
  if (readyPromise) return readyPromise

  const attempt = runReadinessGate(url)
  readyPromise = attempt
  attempt.then(result => {
    if (!result.ready) readyPromise = null
  })
  return attempt
}

/** 仅用于测试与热重载：清掉就绪结果缓存。 */
export function resetBackendReadyGate() {
  readyPromise = null
}
