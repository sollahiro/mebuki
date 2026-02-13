import { useRef } from 'react'
import { Trash2, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useSidebar } from '@/hooks/useSidebar'
import type { HistoryItem } from '@/types'

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
  onHistorySelect: (code: string) => void
  onDelete: (code: string) => void
  onReanalyze: (code: string) => void
  history: HistoryItem[]
  isAnalyzing: boolean
}

export function Sidebar({
  isOpen,
  onClose,
  onHistorySelect,
  onDelete,
  onReanalyze,
  history,
  isAnalyzing,
}: SidebarProps) {
  const sidebarRef = useRef<HTMLDivElement>(null)
  const { handleMouseEnter, handleMouseLeave } = useSidebar({ onClose })

  return (
    <aside
      ref={sidebarRef}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={cn(
        'fixed left-0 top-0 h-screen bg-card border-r border-border',
        'z-[60] shadow-xl transition-all duration-200 ease-out overflow-hidden',
        isOpen ? 'w-72' : 'w-0'
      )}
    >
      <div className="w-72">
        {/* コンテンツ */}
        <div className="p-4 pt-12 space-y-6 overflow-y-auto h-screen scrollbar-thin">
          <div className="space-y-3">
            <div className="space-y-2">
              {history.length === 0 ? (
                <p className="text-sm text-foreground-muted py-4 text-center">
                  キャッシュがありません
                </p>
              ) : (
                // 銘柄コード（先頭4桁）で重複を排除
                history.filter((item, index, self) =>
                  self.findIndex(i => i.code.slice(0, 4) === item.code.slice(0, 4)) === index
                ).map((item) => (
                  <div
                    key={item.code}
                    className={cn(
                      'flex items-center gap-2 px-3 py-2 rounded-md text-sm',
                      'bg-surface',
                      'hover:bg-primary/10',
                      'transition-colors',
                      isAnalyzing && 'opacity-50'
                    )}
                  >
                    <button
                      onClick={() => onHistorySelect(item.code)}
                      disabled={isAnalyzing}
                      className="flex-1 text-left disabled:cursor-not-allowed"
                    >
                      <div className="font-medium text-foreground">
                        {item.code.slice(0, 4)} {item.name}
                      </div>
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        onReanalyze(item.code)
                      }}
                      disabled={isAnalyzing}
                      className={cn(
                        'p-1 rounded hover:bg-primary/10 text-foreground-muted hover:text-primary',
                        'transition-colors',
                        'disabled:opacity-50 disabled:cursor-not-allowed'
                      )}
                      title="最新情報で再分析"
                    >
                      <RefreshCw className="w-4 h-4" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        onDelete(item.code)
                      }}
                      disabled={isAnalyzing}
                      className={cn(
                        'p-1 rounded hover:bg-error/10 text-foreground-muted hover:text-error',
                        'transition-colors',
                        'disabled:opacity-50 disabled:cursor-not-allowed'
                      )}
                      title="キャッシュを削除"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </aside>
  )
}
