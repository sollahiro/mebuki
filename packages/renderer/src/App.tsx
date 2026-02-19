import { useEffect } from 'react'
import { TitleBar } from '@/components/TitleBar'
import { SettingsPage } from '@/components/SettingsPage'
import { useTheme } from '@/hooks/useTheme'
import * as api from './lib/api'

function App() {
  const { theme } = useTheme()

  // テーマをHTMLに適用
  useEffect(() => {
    const root = document.documentElement
    if (theme === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
  }, [theme])

  // 起動時にAPIキーをバックエンドに送信
  useEffect(() => {
    const loadAndSyncSettings = async () => {
      try {
        let settings
        if (window.electronAPI?.getSettings) {
          settings = await window.electronAPI.getSettings()
        } else {
          const stored = localStorage.getItem('mebuki-settings')
          if (stored) settings = JSON.parse(stored)
        }

        if (settings) {
          try {
            await api.updateSettings(settings)
          } catch (err) {
            console.error('バックエンドへの設定送信に失敗しました:', err)
          }
        }
      } catch (err) {
        console.error('設定の同期に失敗しました:', err)
      }
    }

    loadAndSyncSettings()
  }, [])

  return (
    <div className="flex flex-col h-screen bg-background text-foreground">
      <TitleBar />

      {/* メインエリア - 設定画面固定 */}
      <div className="flex flex-1 overflow-hidden relative pt-[48px]">
        <SettingsPage />
      </div>
    </div>
  )
}

export default App
