import { useRef, useCallback, useEffect } from 'react'

interface UseSidebarOptions {
  onClose: () => void
  delay?: number
}

/**
 * サイドバーのマウスイベントハンドラーを提供するカスタムフック
 * タイムアウト付きの自動クローズ機能を実装
 */
export function useSidebar({ onClose, delay = 300 }: UseSidebarOptions) {
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)

  const handleMouseLeave = useCallback(() => {
    // サイドバーから離れた時、指定時間後に閉じる
    timeoutRef.current = setTimeout(() => {
      onClose()
    }, delay)
  }, [onClose, delay])

  const handleMouseEnter = useCallback(() => {
    // サイドバーに入った時、タイムアウトをキャンセル
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
  }, [])

  // クリーンアップ
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [])

  return {
    handleMouseLeave,
    handleMouseEnter,
  }
}
