import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { readFileSync, existsSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'
import os from 'os'

const __dirname = dirname(fileURLToPath(import.meta.url))

function loadServerConfig() {
  const envConfigPath = process.env.SERVER_CONFIG_PATH
  if (envConfigPath && existsSync(envConfigPath)) {
    try {
      return JSON.parse(readFileSync(envConfigPath, 'utf-8'))
    } catch (e) {
      console.warn('Failed to load server config from SERVER_CONFIG_PATH, trying defaults')
    }
  }

  // 优先读取项目根目录的配置
  const projectConfigPath = resolve(__dirname, '../server_config.json')
  if (existsSync(projectConfigPath)) {
    try {
      const configFile = JSON.parse(readFileSync(projectConfigPath, 'utf-8'))
      return configFile
    } catch (e) {
      console.warn('Failed to load server_config.json from project root, trying AppData')
    }
  }
  // 其次读取 AppData 里的配置（与后端一致）
  const appData = process.env.APPDATA || (process.platform === 'darwin'
    ? `${process.env.HOME}/Library/Application Support`
    : `${process.env.HOME}/.config`)
  const appDataConfigPath = resolve(appData, 'ULTIMATE_WEB', 'server_config.json')
  if (existsSync(appDataConfigPath)) {
    try {
      const configFile = JSON.parse(readFileSync(appDataConfigPath, 'utf-8'))
      return configFile
    } catch (e) {
      console.warn('Failed to load server_config.json from AppData, using defaults')
    }
  }
  return {
    backend: { host: '0.0.0.0', port: 5000, ssl_enabled: true },
    frontend: { host: '0.0.0.0', port: 5173 },
    auth: { enabled: false, normal_port: 5001, private_port: 5000 }
  }
}

function resolveSslCertPaths() {
  const appData = process.env.APPDATA || (process.platform === 'darwin'
    ? `${process.env.HOME}/Library/Application Support`
    : `${process.env.HOME}/.config`)
  const sslDir = resolve(appData, 'ULTIMATE_WEB', 'ssl')
  return {
    cert: resolve(sslDir, 'cert.pem'),
    key: resolve(sslDir, 'key.pem')
  }
}

const serverConfig = loadServerConfig()
const frontendConfig = serverConfig.frontend || {}
const backendConfig = serverConfig.backend || {}
const authConfig = serverConfig.auth || {}

// auth 启用时，开发环境默认连接 normal 端口（需要认证）
const authEnabled = !!authConfig.enabled
const backendPort = authEnabled
  ? (authConfig.normal_port || 5001)
  : (backendConfig.port || 5000)

const backendSslEnabled = backendConfig.ssl_enabled !== false
const backendProtocol = backendSslEnabled ? 'https' : 'http'
const backendHost = backendConfig.host === '0.0.0.0' ? '127.0.0.1' : (backendConfig.host || '127.0.0.1')
const backendTarget = `${backendProtocol}://${backendHost}:${backendPort}`

let viteHttpsConfig = false
if (backendSslEnabled) {
  const sslPaths = resolveSslCertPaths()
  if (existsSync(sslPaths.cert) && existsSync(sslPaths.key)) {
    try {
      viteHttpsConfig = {
        key: readFileSync(sslPaths.key),
        cert: readFileSync(sslPaths.cert)
      }
      console.log(`[vite] HTTPS enabled using cert: ${sslPaths.cert}`)
    } catch (e) {
      console.warn('[vite] Failed to load SSL cert, falling back to HTTP')
      viteHttpsConfig = false
    }
  } else {
    console.warn('[vite] SSL cert files not found, Vite dev server will use HTTP')
  }
}

console.log(`[vite] Backend target: ${backendTarget}`)
console.log(`[vite] Auth enabled: ${authEnabled}`)

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    host: frontendConfig.host || '0.0.0.0',
    port: frontendConfig.port || 5173,
    https: viteHttpsConfig,
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
        secure: !backendSslEnabled ? true : false,
        rewrite: (path) => path
      },
      '/static': {
        target: backendTarget,
        changeOrigin: true,
        secure: !backendSslEnabled ? true : false
      },
      '/media': {
        target: backendTarget,
        changeOrigin: true,
        secure: !backendSslEnabled ? true : false
      }
    }
  },
  define: {
    'import.meta.env.VITE_BACKEND_PORT': JSON.stringify(backendPort),
    'import.meta.env.VITE_BACKEND_SSL_ENABLED': JSON.stringify(backendSslEnabled),
    'import.meta.env.VITE_AUTH_ENABLED': JSON.stringify(authEnabled),
    'import.meta.env.VITE_PRIVATE_PORT': JSON.stringify(authConfig.private_port || 5000),
    'import.meta.env.VITE_NORMAL_PORT': JSON.stringify(authConfig.normal_port || 5001)
  }
})
