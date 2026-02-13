import { useState, useEffect, useCallback, useRef } from 'react'
import { X, Key, Eye, EyeOff, AlertCircle, CheckCircle, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import * as Dialog from '@radix-ui/react-dialog'
import { getApiUrl } from '@/lib/api'

interface SettingsDialogProps {
  isOpen: boolean
  onClose: () => void
}

interface SettingsForm {
  jquantsApiKey: string
  edinetApiKey: string
  mcpEnabled: boolean
}

export function SettingsDialog({ isOpen, onClose }: SettingsDialogProps) {
  const [settings, setSettings] = useState<SettingsForm>({
    jquantsApiKey: '',
    edinetApiKey: '',
    mcpEnabled: true,
  })
  const [showKeys, setShowKeys] = useState({
    jquantsApiKey: false,
    edinetApiKey: false,
  })
  const [isSaving, setIsSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState('')

  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
  const saveTimerRef = useRef<NodeJS.Timeout | null>(null)
  const isFirstLoad = useRef(true)

  // Electronのストアから設定を読み込む
  useEffect(() => {
    if (isOpen) {
      loadSettings()
    }
  }, [isOpen])



  const loadSettings = async () => {
    try {
      // Electron APIが利用可能な場合
      if (window.electronAPI?.getSettings) {
        const stored = await window.electronAPI.getSettings()
        setSettings({
          jquantsApiKey: stored.jquantsApiKey || '',
          edinetApiKey: stored.edinetApiKey || '',
          mcpEnabled: true,
        })
      } else {
        // ローカルストレージから読み込む（Web版フォールバック）
        const stored = localStorage.getItem('mebuki-settings')
        if (stored) {
          const parsed = JSON.parse(stored)
          setSettings({
            ...parsed,
            mcpEnabled: true,
          })
        }
      }
    } catch (err) {
      console.error('設定の読み込みに失敗しました:', err)
    }
  }

  const triggerAutoSave = useCallback((updatedSettings: SettingsForm) => {
    setHasUnsavedChanges(true)
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)

    saveTimerRef.current = setTimeout(async () => {
      setIsSaving(true)
      setSaveStatus('idle')
      setErrorMessage('')

      try {
        if (window.electronAPI?.saveSettings) {
          await window.electronAPI.saveSettings(updatedSettings)
        } else {
          localStorage.setItem('mebuki-settings', JSON.stringify(updatedSettings))
        }

        const response = await fetch(getApiUrl('/api/settings'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(updatedSettings),
        })

        if (!response.ok) {
          throw new Error('サーバーへの設定送信に失敗しました')
        }

        setSaveStatus('success')
        setHasUnsavedChanges(false)
        setTimeout(() => setSaveStatus('idle'), 2000)
      } catch (err) {
        setSaveStatus('error')
        setErrorMessage(err instanceof Error ? err.message : '保存に失敗しました')
      } finally {
        setIsSaving(false)
      }
    }, 800)
  }, [])

  // 自動保存のトリガー
  useEffect(() => {
    if (isFirstLoad.current) {
      if (settings.jquantsApiKey !== '' || settings.edinetApiKey !== '') {
        isFirstLoad.current = false
      }
      return
    }
    triggerAutoSave(settings)
  }, [settings, triggerAutoSave])


  const toggleShowKey = (key: keyof typeof showKeys) => {
    setShowKeys((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  return (
    <Dialog.Root open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-lg bg-card rounded-lg shadow-xl z-50 max-h-[90vh] overflow-y-auto">
          {/* ヘッダー */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-border">
            <div className="flex items-center gap-3">
              <Dialog.Title className="text-lg font-semibold text-foreground">
                設定
              </Dialog.Title>
              <div className="text-xs">
                {isSaving ? (
                  <span className="text-foreground-muted animate-pulse">保存中...</span>
                ) : hasUnsavedChanges ? (
                  <span className="text-foreground-muted">入力中...</span>
                ) : saveStatus === 'success' ? (
                  <span className="text-success flex items-center gap-1 font-medium">
                    <CheckCircle className="w-3.5 h-3.5" />
                    保存済み
                  </span>
                ) : saveStatus === 'error' ? (
                  <span className="text-error flex items-center gap-1 font-medium">
                    <AlertCircle className="w-3.5 h-3.5" />
                    保存エラー
                  </span>
                ) : null}
              </div>
            </div>
            <Dialog.Close asChild>
              <Button variant="ghost" size="icon">
                <X className="w-5 h-5" />
              </Button>
            </Dialog.Close>
          </div>

          {/* コンテンツ */}
          <div className="p-6 space-y-6">
            {/* ステータスメッセージ */}
            {saveStatus === 'success' && (
              <div className="flex items-center gap-2 p-3 bg-success/10 border border-success/20 rounded-lg text-success">
                <CheckCircle className="w-5 h-5" />
                <span className="text-sm">設定を保存しました</span>
              </div>
            )}
            {saveStatus === 'error' && (
              <div className="flex items-center gap-2 p-3 bg-error/10 border border-error/20 rounded-lg text-error">
                <AlertCircle className="w-5 h-5" />
                <span className="text-sm">{errorMessage}</span>
              </div>
            )}

            {/* J-QUANTS API Key */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground flex items-center gap-2">
                <Key className="w-4 h-4" />
                J-QUANTS APIキー
                <span className="text-error">*</span>
              </label>
              <div className="relative">
                <input
                  type={showKeys.jquantsApiKey ? 'text' : 'password'}
                  value={settings.jquantsApiKey}
                  onChange={(e) =>
                    setSettings((prev) => ({ ...prev, jquantsApiKey: e.target.value }))
                  }
                  placeholder="APIキーを入力"
                  className={cn(
                    'w-full px-4 py-2 pr-10 rounded-md border border-border',
                    'bg-input',
                    'text-foreground placeholder:text-foreground-muted',
                    'focus:outline-none focus:ring-2 focus:ring-primary'
                  )}
                />
                <button
                  type="button"
                  onClick={() => toggleShowKey('jquantsApiKey')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-foreground-muted hover:text-foreground"
                >
                  {showKeys.jquantsApiKey ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
              <div className="flex items-center justify-between">
                <p className="text-xs text-foreground-muted">
                  財務データ取得に必要です（必須）
                </p>
                <a
                  href="https://jpx-jquants.com/ja"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] text-primary hover:underline flex items-center gap-1"
                >
                  登録・発行サイトへ
                  <ExternalLink className="w-2.5 h-2.5" />
                </a>
              </div>
            </div>

            {/* EDINET API Key */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground flex items-center gap-2">
                <Key className="w-4 h-4" />
                EDINET APIキー
              </label>
              <div className="relative">
                <input
                  type={showKeys.edinetApiKey ? 'text' : 'password'}
                  value={settings.edinetApiKey}
                  onChange={(e) =>
                    setSettings((prev) => ({ ...prev, edinetApiKey: e.target.value }))
                  }
                  placeholder="APIキーを入力"
                  className={cn(
                    'w-full px-4 py-2 pr-10 rounded-md border border-border',
                    'bg-input',
                    'text-foreground placeholder:text-foreground-muted',
                    'focus:outline-none focus:ring-2 focus:ring-primary'
                  )}
                />
                <button
                  type="button"
                  onClick={() => toggleShowKey('edinetApiKey')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-foreground-muted hover:text-foreground"
                >
                  {showKeys.edinetApiKey ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
              <div className="flex items-center justify-between">
                <p className="text-xs text-foreground-muted">
                  有価証券報告書の取得に必要です（必須）
                </p>
                <a
                  href="https://api.edinet-fsa.go.jp/api/auth/index.aspx?mode=1"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] text-primary hover:underline flex items-center gap-1"
                >
                  登録・発行サイトへ
                  <ExternalLink className="w-2.5 h-2.5" />
                </a>
              </div>
            </div>

          </div>

          {/* フッター */}
          <div className="flex justify-end items-center px-6 py-4 border-t border-border bg-surface/50">
            <Button variant="outline" onClick={onClose}>
              閉じる
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
