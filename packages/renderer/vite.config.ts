import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'
import path from 'path'

const isMcp = process.env.BUILD_TARGET === 'mcp'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    ...(isMcp ? [viteSingleFile()] : [])
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  base: './', // Electron用の相対パス
  build: {
    outDir: 'dist',
    emptyOutDir: !isMcp, // MCPビルド時は既存のファイルを消さない
    // CSSの最適化設定
    cssCodeSplit: !isMcp,
    // アセットのインライン化 (MCPのみ最大限行う)
    assetsInlineLimit: isMcp ? 100000000 : 4096,
    // ソースマップを非表示
    sourcemap: false,
    rollupOptions: {
      input: isMcp
        ? path.resolve(__dirname, 'mcp.html')
        : path.resolve(__dirname, 'index.html'),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765', // FastAPIサーバーのポートに合わせてください
        changeOrigin: true,
      },
    },
  },
})
