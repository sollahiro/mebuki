import { useState, useEffect } from 'react'
import { Loader2, X, Clock } from 'lucide-react'
import * as Dialog from '@radix-ui/react-dialog'
import { Button } from '@/components/ui/Button'
import type { ProgressState } from '@/types'

interface AnalysisProgressDialogProps {
  isOpen: boolean
  progress: ProgressState
  onCancel: () => void
}

export function AnalysisProgressDialog({
  isOpen,
  progress,
  onCancel,
}: AnalysisProgressDialogProps) {
  const [elapsedTime, setElapsedTime] = useState(0)
  const [startTime, setStartTime] = useState<number | null>(null)

  // 経過時間のカウントアップ
  useEffect(() => {
    if (isOpen && startTime === null) {
      setStartTime(Date.now())
      setElapsedTime(0)
    } else if (!isOpen) {
      setStartTime(null)
      setElapsedTime(0)
    }

    if (!isOpen || startTime === null) {
      return
    }

    const interval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTime) / 1000)
      setElapsedTime(elapsed)
    }, 1000)

    return () => clearInterval(interval)
  }, [isOpen, startTime])

  // 経過時間をフォーマット（秒 → MM:SS）
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <Dialog.Root open={isOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/30 backdrop-blur-[2px] z-[60]" />
        <Dialog.Content className="fixed top-10 left-1/2 -translate-x-1/2 w-full max-w-md bg-card/95 backdrop-blur-md rounded-xl shadow-2xl z-[70] p-6 outline-none animate-in fade-in slide-in-from-top-4 duration-300">
          <div className="flex flex-col items-center text-center">
            <div className="flex items-center gap-4 w-full mb-4">
              <div className="bg-brand-start/10 p-2 rounded-full">
                <Loader2 className="w-6 h-6 text-brand-start animate-spin" />
              </div>
              <Dialog.Title className="text-lg font-bold text-foreground">
                分析を実行中...
              </Dialog.Title>
            </div>

            {/* 銘柄情報 */}
            {(progress.company_code || progress.company_name) && (
              <div className="mb-6 px-4 py-2 bg-surface rounded-lg border border-border">
                {progress.company_code && (
                  <span className="text-xs font-mono text-foreground-muted block mb-1">
                    {progress.company_code}
                  </span>
                )}
                {progress.company_name && (
                  <span className="text-sm font-semibold text-foreground">
                    {progress.company_name}
                  </span>
                )}
              </div>
            )}

            {/* 現在のステップ */}
            <div className="w-full space-y-4 mb-8">
              <div className="flex justify-between text-xs mb-1 px-1">
                <span className="text-primary font-medium">{progress.step || '準備中'}</span>
                <span className="text-foreground-muted font-mono">{progress.progress}%</span>
              </div>

              {/* プログレスバー */}
              <div className="h-2.5 bg-border rounded-full overflow-hidden">
                <div
                  className="h-full bg-mebuki-brand transition-all duration-500 ease-out shadow-[0_0_12px_rgba(53,200,95,0.5)]"
                  style={{ width: `${progress.progress}%` }}
                />
              </div>

              <p className="text-sm text-foreground-muted leading-relaxed min-h-[1.25rem]">
                {progress.message}
              </p>
            </div>

            {/* 下部情報と操作 */}
            <div className="w-full flex items-center justify-between pt-2">
              <div className="flex items-center gap-1.5 text-foreground-muted">
                <Clock className="w-3.5 h-3.5" />
                <span className="text-xs font-mono">{formatTime(elapsedTime)}</span>
              </div>

              <Button
                variant="outline"
                size="sm"
                onClick={onCancel}
                className="hover:bg-error/10 hover:text-error hover:border-error/30 transition-colors"
              >
                <X className="w-4 h-4 mr-2" />
                分析を中止
              </Button>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
