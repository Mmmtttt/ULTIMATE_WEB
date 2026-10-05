import fs from 'node:fs'
import http from 'node:http'
import https from 'node:https'
import os from 'node:os'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { createServer as createViteServer } from 'vite'

const rootDir = path.dirname(fileURLToPath(import.meta.url))

function appDataDir() {
  if (process.env.APPDATA) return process.env.APPDATA
  if (process.platform === 'darwin') return path.join(process.env.HOME || os.homedir(), 'Library', 'Application Support')
  return path.join(process.env.HOME || os.homedir(), '.config')
}

function loadServerConfig() {
  const candidates = [
    process.env.SERVER_CONFIG_PATH,
    path.join(rootDir, '..', 'server_config.json'),
    path.join(appDataDir(), 'ULTIMATE_WEB', 'server_config.json')
  ].filter(Boolean)

  for (const candidate of candidates) {
    try {
      return JSON.parse(fs.readFileSync(candidate, 'utf8'))
    } catch (_) {
      // Follow the same fallback order as vite.config.js.
    }
  }
  return {}
}

function loadSslOptions(serverConfig) {
  if (serverConfig.backend?.ssl_enabled === false) return null
  const sslDir = path.join(appDataDir(), 'ULTIMATE_WEB', 'ssl')
  const cert = path.join(sslDir, 'cert.pem')
  const key = path.join(sslDir, 'key.pem')
  if (!fs.existsSync(cert) || !fs.existsSync(key)) return null
  return { cert: fs.readFileSync(cert), key: fs.readFileSync(key) }
}

function cliValue(name) {
  const index = process.argv.indexOf(name)
  return index >= 0 ? process.argv[index + 1] : undefined
}

const serverConfig = loadServerConfig()
const ssl = loadSslOptions(serverConfig)
const transport = ssl ? https.createServer(ssl) : http.createServer()
const cliHost = cliValue('--host')
const cliPort = Number(cliValue('--port'))
const cliStrictPort = process.argv.includes('--strictPort')

// Vite 8 uses an HTTP/2 secure server for server.https. Running Vite as
// middleware behind Node's HTTPS server keeps the development URL HTTPS while
// giving Vite and its proxy the normal HTTP/1.1 request objects they expect.
const vite = await createViteServer({
  root: rootDir,
  server: {
    middlewareMode: true,
    https: false,
    ...(cliHost ? { host: cliHost } : {}),
    ...(Number.isFinite(cliPort) && cliPort > 0 ? { port: cliPort } : {}),
    ...(cliStrictPort ? { strictPort: true } : {}),
    hmr: { server: transport }
  }
})

transport.on('request', vite.middlewares)
transport.on('error', (error) => {
  console.error(`[dev server] ${error.message}`)
  process.exitCode = 1
})

const host = cliHost || vite.config.server.host || '0.0.0.0'
const port = Number.isFinite(cliPort) && cliPort > 0 ? cliPort : vite.config.server.port

await new Promise((resolve, reject) => {
  const onError = (error) => {
    transport.off('listening', onListening)
    reject(error)
  }
  const onListening = () => {
    transport.off('error', onError)
    resolve()
  }
  transport.once('error', onError)
  transport.once('listening', onListening)
  transport.listen(port, host)
})

console.log(`[dev server] ${ssl ? 'https' : 'http'}://${host}:${port}/`)

async function close() {
  await vite.close()
  await new Promise((resolve) => transport.close(resolve))
}

process.once('SIGINT', () => close().finally(() => process.exit(0)))
process.once('SIGTERM', () => close().finally(() => process.exit(0)))
