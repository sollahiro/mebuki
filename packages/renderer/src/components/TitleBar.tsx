import { Settings, Glasses } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { TopSearchBar } from '@/components/TopSearchBar'

interface TitleBarProps {
  onSearch: (code: string) => void
  onSettingsClick: () => void
  onHomeClick?: () => void
  isAnalyzing?: boolean
  analysisMessage?: string
  onCancel?: () => void
  showSearch?: boolean
}

export function TitleBar({
  onSearch,
  onSettingsClick,
  onHomeClick,
  isAnalyzing,
  analysisMessage,
  onCancel,
  showSearch = true
}: TitleBarProps) {
  return (
    <header
      className="fixed top-0 left-0 right-0 h-[48px] z-50 flex items-center justify-between px-2 select-none border-b border-border/40 bg-background/80 backdrop-blur-sm"
      style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
    >
      {/* 左側：macOSの信号機ボタン用のスペース */}
      <div className="w-20 h-full flex items-center" />

      {/* 中央：検索バー */}
      <div
        className="flex-1 flex justify-center items-center h-full px-4"
        style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
      >
        {showSearch && (
          <TopSearchBar
            onSearch={onSearch}
            isAnalyzing={isAnalyzing}
            analysisMessage={analysisMessage}
            onCancel={onCancel}
          />
        )}
      </div>

      {/* 右側：アイコンボタン */}
      <div
        className="flex items-center justify-end w-auto h-full gap-2"
        style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
      >
        {/* 検索ボタン（メガネアイコン） */}
        <Button
          variant="ghost"
          size="icon"
          onClick={onHomeClick}
          className="text-foreground-muted hover:text-foreground h-8 w-8"
        >
          <Glasses className="w-[18px] h-[18px]" />
          <span className="sr-only">ホーム</span>
        </Button>

        {/* ポートフォリオページボタン（円グラフアイコン・準備中）
        <Button
          variant="ghost"
          size="icon"
          disabled
          className="text-foreground-muted hover:text-foreground h-8 w-8 opacity-30 cursor-not-allowed"
        >
          <PieChart className="w-[18px] h-[18px]" />
          <span className="sr-only">ポートフォリオ（準備中）</span>
        </Button>
        */}

        {/* 設定ボタン（歯車アイコン） */}
        <Button
          variant="ghost"
          size="icon"
          onClick={onSettingsClick}
          className="text-foreground-muted hover:text-foreground h-8 w-8"
        >
          <Settings className="w-[18px] h-[18px]" />
          <span className="sr-only">設定</span>
        </Button>
      </div>
    </header>
  )
}
