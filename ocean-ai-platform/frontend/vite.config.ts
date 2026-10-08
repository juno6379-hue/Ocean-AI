// 파일 역할: 프런트엔드 개발 서버와 빌드 설정을 정의합니다.
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  // Match the documented FastAPI port; API_PROXY_TARGET remains an explicit override.
  server: { proxy: { "/api": { target: loadEnv(mode, process.cwd(), "").API_PROXY_TARGET || "http://127.0.0.1:8000", changeOrigin: true } } },
  plugins: [
    tailwindcss(),
    react()
  ],
}))
