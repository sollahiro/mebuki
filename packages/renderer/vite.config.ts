import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
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
    // アセットのインライン化を無効化（フォントや画像が正しく読み込まれるように）
    assetsInlineLimit: 0,
    // ソースマップを生成（デバッグ用）
    sourcemap: false,
    // チャンクサイズの警告を無効化
    chunkSizeWarningLimit: 1000,
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
