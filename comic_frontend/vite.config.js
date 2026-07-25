import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { readFileSync, existsSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'
import os from 'os'

const __dirname = dirname(fileURLToPath(import.meta.url))

function loadServerConfig() {
  const configPath = resolve(__dirname, '../server_config.json')
  if (existsSync(configPath)) {
    try {
      const configFile = JSON.parse(readFileSync(configPath, 'utf-8'))
      return configFile
    } catch (e) {
      console.warn('Failed to load server_config.json, using defaults')
    }
  }
  return {
    backend: { host: '0.0.0.0', port: 5000, ssl_enabled: true },
    frontend: { host: '0.0.0.0', port: 5173 }
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
const backendPort = backendConfig.port || 5000
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
    'import.meta.env.VITE_BACKEND_SSL_ENABLED': JSON.stringify(backendSslEnabled)
  }
})
