import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  base: './', // Electron用の相対パス
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    // CSSの最適化設定
    cssCodeSplit: false,
    // アセットのインライン化
    assetsInlineLimit: 100000000,
    // ソースマップを非表示
    sourcemap: false,
    rollupOptions: {
      input: path.resolve(__dirname, 'mcp.html'),
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
