import { defineConfig, mergeConfig } from "../comic_frontend/node_modules/vite/dist/node/index.js";
import baseConfig from "../comic_frontend/vite.config.js";

const backendPort = Number.parseInt(process.env.PW_BACKEND_PORT || "5010", 10);
const frontendPort = Number.parseInt(process.env.PW_FRONTEND_PORT || "4174", 10);

export default mergeConfig(
  baseConfig,
  defineConfig({
    server: {
      host: "127.0.0.1",
      port: frontendPort,
      proxy: {
        "/api": {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: true,
          rewrite: (path) => path,
        },
        "/static": {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: true,
        },
        "/media": {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: true,
        },
      },
    },
    define: {
      "import.meta.env.VITE_BACKEND_PORT": JSON.stringify(backendPort),
    },
  }),
);
