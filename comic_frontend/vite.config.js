import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { readFileSync, existsSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

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
  return { backend: { host: '0.0.0.0', port: 5000 }, frontend: { host: '0.0.0.0', port: 5173 } }
}

const serverConfig = loadServerConfig()
const frontendConfig = serverConfig.frontend || {}
const backendConfig = serverConfig.backend || {}
const backendPort = backendConfig.port || 5000

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
    proxy: {
      '/api': {
        target: `http://${backendConfig.host === '0.0.0.0' ? '127.0.0.1' : backendConfig.host}:${backendPort}`,
        changeOrigin: true,
        rewrite: (path) => path
      },
      '/static': {
        target: `http://${backendConfig.host === '0.0.0.0' ? '127.0.0.1' : backendConfig.host}:${backendPort}`,
        changeOrigin: true
      }
    }
  },
  define: {
    'import.meta.env.VITE_BACKEND_PORT': JSON.stringify(backendPort)
  }
})
