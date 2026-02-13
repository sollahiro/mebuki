import { useState, useEffect } from 'react'
import { ChevronRight, AlertCircle } from 'lucide-react'
import { AnalysisResults } from '@/components/AnalysisResults'
import { cn } from '@/lib/utils'
import type { AnalysisResult } from '@/types'

interface MainContentProps {
  results: AnalysisResult[]
  isAnalyzing: boolean
  error: string | null
  sidebarOpen: boolean
  onCancel?: () => void
}

export function MainContent({
  results,
  isAnalyzing,
  error,
  sidebarOpen,
}: MainContentProps) {
  const [startTime, setStartTime] = useState<number | null>(null)

  useEffect(() => {
    if (isAnalyzing && startTime === null) {
      setStartTime(Date.now())
    } else if (!isAnalyzing) {
      setStartTime(null)
    }
  }, [isAnalyzing, startTime])

  const isInitialState = !isAnalyzing && results.length === 0 && !error

  return (
    <main className="flex-1 flex flex-col overflow-y-auto transition-all duration-200 ease-out relative">
      {/* サイドバー展開時のカーテン（暗調化レイヤー） */}
      <div
        className={cn(
          'fixed inset-0 bg-black/30 z-50 transition-opacity duration-300 pointer-events-none',
          sidebarOpen ? 'opacity-100' : 'opacity-0'
        )}
      />

      {/* トリガーゾーン（左端でサイドバーを開く） */}
      <div className={cn(
        'fixed top-0 left-0 w-5 h-screen z-30'
      )} />

      {/* コンテンツエリア */}
      <div className="p-6 max-w-7xl mx-auto w-full transition-all duration-200 ease-out">
        {/* エラー表示 */}
        {error && (
          <div className="mb-6 p-4 rounded-lg bg-error/10 border border-error/20 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-error flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-error">エラーが発生しました</p>
              <p className="text-sm text-foreground-muted mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* 分析結果リスト */}
        <div className="space-y-12">
          {results.map((result) => (
            <div key={result.code} className="animate-in fade-in slide-in-from-bottom-4 duration-500">
              <AnalysisResults
                result={result}
                isAnalyzing={result.status !== 'complete' && result.status !== 'error'}
              />
            </div>
          ))}
        </div>

        {/* 初期状態 */}
        {isInitialState && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="w-16 h-16 rounded-full bg-surface flex items-center justify-center mb-6">
              <ChevronRight className="w-8 h-8 text-foreground-muted" />
            </div>
            <h2 className="text-xl font-medium text-foreground mb-4">
              銘柄を分析しましょう
            </h2>
            <div className="text-foreground-muted max-w-lg space-y-2 text-left bg-surface p-6 rounded-lg border border-border">
              <p>① 右上の歯車ボタンでAPIキーを設定。</p>
              <p>② 企業名または銘柄コードを入力して分析を開始。</p>
              <p>③ 画面左端にカーソルを移動すると、分析した銘柄一覧が表示されます。</p>
            </div>
          </div>
        )}
      </div>
    </main>
  )
}
