import { useState, useRef, KeyboardEvent, ClipboardEvent, ChangeEvent } from 'react'
import { Search, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/Button'

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

interface StockCodeInputProps {
  onSubmit: (code: string) => void
  disabled?: boolean
}

export function StockCodeInput({ onSubmit, disabled }: StockCodeInputProps) {
  const [values, setValues] = useState(['', '', '', ''])
  const inputRefs = [
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null),
    useRef<HTMLInputElement>(null),
  ]

  const handleChange = (index: number, value: string) => {
    // 全角英数字を半角に変換してから、英数字のみ許可
    const alphanumericValue = toHalfWidthUpper(value).replace(/[^0-9A-Z]/g, '').slice(0, 1)

    const newValues = [...values]
    newValues[index] = alphanumericValue
    setValues(newValues)

    // 入力があったら次のボックスへ
    if (alphanumericValue && index < 3) {
      inputRefs[index + 1].current?.focus()
    }
  }

  const handleKeyDown = (index: number, e: KeyboardEvent<HTMLInputElement>) => {
    // Backspaceで前のボックスに戻る
    if (e.key === 'Backspace' && !values[index] && index > 0) {
      inputRefs[index - 1].current?.focus()
    }

    // Enterで送信
    if (e.key === 'Enter') {
      handleSubmit()
    }

    // 矢印キーで移動
    if (e.key === 'ArrowLeft' && index > 0) {
      inputRefs[index - 1].current?.focus()
    }
    if (e.key === 'ArrowRight' && index < 3) {
      inputRefs[index + 1].current?.focus()
    }
  }

  const handlePaste = (e: ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault()
    // 全角英数字を半角に変換してから、英数字のみ抽出
    const pastedData = toHalfWidthUpper(e.clipboardData.getData('text')).replace(/[^0-9A-Z]/g, '').slice(0, 4)

    if (pastedData.length > 0) {
      const newValues = [...values]
      for (let i = 0; i < 4; i++) {
        newValues[i] = pastedData[i] || ''
      }
      setValues(newValues)

      // 最後の入力ボックスにフォーカス
      const lastIndex = Math.min(pastedData.length, 4) - 1
      if (lastIndex >= 0) {
        inputRefs[lastIndex].current?.focus()
      }
    }
  }

  const handleSubmit = () => {
    const code = values.join('')
    if (code.length === 4 && !disabled) {
      onSubmit(code)
    }
  }

  const isComplete = values.every((v) => v !== '')

  return (
    <div className="space-y-3">
      {/* 4桁ボックス入力 */}
      <div className="flex gap-2 justify-center">
        {values.map((value, index) => (
          <input
            key={index}
            ref={inputRefs[index]}
            type="text"
            inputMode="text"
            pattern="[0-9A-Z]"
            maxLength={1}
            value={value}
            onChange={(e: ChangeEvent<HTMLInputElement>) => handleChange(index, e.target.value)}
            onKeyDown={(e) => handleKeyDown(index, e)}
            onPaste={handlePaste}
            disabled={disabled}
            placeholder="0"
            className={cn(
              'w-12 h-14 text-center text-2xl font-bold font-mono',
              'border-2 rounded-lg transition-all',
              'bg-input',
              'text-foreground placeholder:text-foreground-muted/40',
              'focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary',
              value ? 'border-primary' : 'border-border',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          />
        ))}
      </div>

      {/* 分析ボタン */}
      <Button
        onClick={handleSubmit}
        disabled={!isComplete || disabled}
        className="w-full"
      >
        {disabled ? (
          <>
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            分析中...
          </>
        ) : (
          <>
            <Search className="w-4 h-4 mr-2" />
            分析
          </>
        )}
      </Button>
    </div>
  )
}
