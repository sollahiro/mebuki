import { useState, KeyboardEvent, useEffect, useRef } from 'react'
import { Search, X, Loader2, Building2 } from 'lucide-react'
import { cn } from '../lib/utils'
import { Button } from '@/components/ui/Button'
import { searchCompanies } from '../lib/api'

// 全角英数字を半角に変換し、大文字化
const toHalfWidthUpper = (str: string): string => {
  return str.replace(/[０-９Ａ-Ｚａ-ｚ]/g, (char) => {
    const code = char.charCodeAt(0)
    if (code >= 0xFF10 && code <= 0xFF19) { // ０-９
      return String.fromCharCode(code - 0xFEE0)
    }
    if (code >= 0xFF21 && code <= 0xFF3A) { // Ａ-Ｚ
      return String.fromCharCode(code - 0xFEE0)
    }
    if (code >= 0xFF41 && code <= 0xFF5A) { // ａ-ｚ
      return String.fromCharCode(code - 0xFEE0 - 32)
    }
    return char
  }).toUpperCase()
}

interface CompanySuggestion {
  code: string
  name: string
  sector: string
  market: string
}

interface TopSearchBarProps {
  onSearch: (code: string) => void
  isAnalyzing?: boolean
  analysisMessage?: string
  onCancel?: () => void
}

export function TopSearchBar({ onSearch, isAnalyzing, analysisMessage, onCancel }: TopSearchBarProps) {
  const [value, setValue] = useState('')
  const [isFocused, setIsFocused] = useState(false)
  const [suggestions, setSuggestions] = useState<CompanySuggestion[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(-1)

  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // クリック外判定
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setShowSuggestions(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // サジェストの取得（デバウンス制御）
  useEffect(() => {
    const timer = setTimeout(async () => {
      if (value.trim().length >= 1 && isFocused) {
        setIsLoading(true)
        try {
          const results = await searchCompanies(value)
          setSuggestions(results)
          setShowSuggestions(results.length > 0)
          setSelectedIndex(-1)
        } catch (error) {
          console.error('Failed to fetch suggestions:', error)
          setSuggestions([])
        } finally {
          setIsLoading(false)
        }
      } else {
        setSuggestions([])
        setShowSuggestions(false)
      }
    }, 300)

    return () => clearTimeout(timer)
  }, [value, isFocused])

  const handleSelect = (code: string) => {
    const normalizedCode = toHalfWidthUpper(code).replace(/[^0-9A-Z]/g, '')
    onSearch(normalizedCode)
    setValue('')
    setShowSuggestions(false)
    inputRef.current?.blur()
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      if (selectedIndex >= 0 && suggestions[selectedIndex]) {
        handleSelect(suggestions[selectedIndex].code)
      } else {
        const code = toHalfWidthUpper(value).replace(/[^0-9A-Z]/g, '')
        if (code.length === 4 || code.length === 5) {
          handleSelect(code)
        }
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(prev => (prev < suggestions.length - 1 ? prev + 1 : prev))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(prev => (prev > 0 ? prev - 1 : -1))
    } else if (e.key === 'Escape') {
      setShowSuggestions(false)
    }
  }

  const showCenteredPlaceholder = !isFocused && !value && !isAnalyzing

  return (
    <div
      ref={containerRef}
      className="relative flex items-center max-w-[400px] w-full gap-2"
      style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
    >
      <div className="relative flex-1 h-[30px]">
        <input
          ref={inputRef}
          type="text"
          value={value}
          onFocus={() => setIsFocused(true)}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isAnalyzing}
          placeholder={isAnalyzing ? "" : (!showCenteredPlaceholder ? "企業名または銘柄コードを入力" : "")}
          className={cn(
            "w-full h-full rounded-md transition-all text-xs text-foreground",
            "bg-surface border border-border",
            "focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary",
            (showCenteredPlaceholder || isAnalyzing) ? "text-center" : "pl-9 pr-8",
            "disabled:opacity-80"
          )}
        />

        {/* 分析中の表示 */}
        {isAnalyzing && (
          <div className="absolute inset-y-0 inset-x-0 flex items-center justify-center pointer-events-none gap-2 px-3">
            <Loader2 className="w-[14px] h-[14px] animate-spin text-primary" />
            <span className="text-xs font-medium text-foreground truncate">
              {analysisMessage || "分析中..."}
            </span>
          </div>
        )}

        {/* 中央配置のプレースホルダー（未入力・未フォーカス時・分析中でない時） */}
        {!isAnalyzing && showCenteredPlaceholder && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none gap-1.5 text-foreground-muted/50">
            <Search className="w-[16px] h-[16px]" />
            <span className="text-xs">企業名または銘柄コードを入力</span>
          </div>
        )}

        {/* 通常の検索アイコン */}
        {!isAnalyzing && !showCenteredPlaceholder && (
          <div className="absolute left-2.5 inset-y-0 flex items-center text-foreground-muted/50 pointer-events-none">
            <Search className="w-[16px] h-[16px]" />
          </div>
        )}

        {/* ローディングアイコン (サジェスト取得中) */}
        {!isAnalyzing && isLoading && (
          <div className="absolute right-2.5 inset-y-0 flex items-center text-primary pointer-events-none">
            <Loader2 className="w-[14px] h-[14px] animate-spin" />
          </div>
        )}

        {/* 入力クリアボタン */}
        {!isAnalyzing && !showCenteredPlaceholder && value && !isLoading && (
          <button
            onClick={() => { setValue(''); setSuggestions([]); setShowSuggestions(false); }}
            className="absolute right-2.5 inset-y-0 flex items-center text-foreground-muted/50 hover:text-foreground transition-colors"
          >
            <X className="w-[14px] h-[14px]" />
          </button>
        )}

        {/* サジェストドロップダウン */}
        {showSuggestions && (
          <div className={cn(
            "absolute top-full left-0 right-0 mt-1.5 z-50",
            "bg-surface/95 backdrop-blur-xl border border-border shadow-2xl rounded-lg overflow-hidden",
            "animate-in fade-in slide-in-from-top-1 duration-200"
          )}>
            <div className="max-h-[300px] overflow-y-auto py-1 custom-scrollbar">
              {suggestions.map((s, i) => (
                <div
                  key={s.code}
                  className={cn(
                    "px-3 py-2 cursor-pointer flex items-center gap-3 transition-colors",
                    selectedIndex === i ? "bg-primary/20 text-primary" : "hover:bg-primary/10 text-foreground"
                  )}
                  onClick={() => handleSelect(s.code)}
                  onMouseEnter={() => setSelectedIndex(i)}
                >
                  <Building2 className="w-4 h-4 opacity-50 flex-shrink-0" />
                  <div className="flex flex-col flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-bold text-xs truncate">{s.name}</span>
                      <span className="text-[10px] font-mono text-foreground-muted bg-surface-muted px-1 rounded">
                        {s.code}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[10px] text-foreground-muted truncate">{s.sector}</span>
                      <span className="text-[10px] text-primary/60 truncate uppercase">{s.market}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 中止ボタン */}
      {isAnalyzing && onCancel && (
        <Button
          variant="outline"
          size="sm"
          onClick={onCancel}
          className="h-[30px] px-3 text-[10px] font-bold border-error/30 text-error hover:bg-error/10 flex-shrink-0"
        >
          <X className="w-3 h-3 mr-1" />
          中止
        </Button>
      )}
    </div>
  )
}
