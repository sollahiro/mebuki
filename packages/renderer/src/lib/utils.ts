import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Tailwindクラスをマージするユーティリティ関数
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * 数値をフォーマット（百万円単位）
 */
export function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-'

  const absValue = Math.abs(value)
  const sign = value < 0 ? '-' : ''

  if (absValue >= 1e12) {
    return `${sign}${(absValue / 1e12).toFixed(1)}兆円`
  }
  if (absValue >= 1e8) {
    return `${sign}${(absValue / 1e8).toFixed(1)}億円`
  }
  if (absValue >= 1e4) {
    return `${sign}${(absValue / 1e4).toFixed(1)}万円`
  }
  return `${sign}${absValue.toLocaleString()}円`
}

/**
 * 数値を百万円単位でフォーマット
 * J-QUANTS APIからのデータは百万円単位で提供される
 */
export function formatMillions(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-'

  // カンマ区切りで百万円単位のまま表示
  const rounded = Math.round(value)
  return `${rounded.toLocaleString()}`
}

/**
 * パーセンテージをフォーマット
 */
export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-'
  return `${value.toFixed(1)}%`
}

/**
 * 倍率をフォーマット
 */
export function formatRatio(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-'
  return `${value.toFixed(2)}倍`
}

/**
 * 日付をフォーマット
 */
export function formatDate(dateStr: string): string {
  if (!dateStr) return '-'

  try {
    const date = new Date(dateStr)
    return date.toLocaleDateString('ja-JP', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  } catch {
    return dateStr
  }
}

/**
 * 年度終了日から年度を抽出
 */
export function extractFiscalYear(fyEnd: string, fyStart?: string): string {
  if (!fyEnd && !fyStart) return '-'

  try {
    // 1. 期首日がある場合はその年を最優先
    if (fyStart) {
      if (fyStart.includes('-')) {
        return `${fyStart.split('-')[0]}年度`
      } else if (fyStart.length >= 4) {
        return `${fyStart.substring(0, 4)}年度`
      }
    }

    // 2. 期末日からの推論 (Fallback)
    let year: number
    let month: number

    if (fyEnd.includes('-')) {
      const parts = fyEnd.split('-')
      year = parseInt(parts[0])
      month = parseInt(parts[1])
    } else if (fyEnd.length >= 8) {
      year = parseInt(fyEnd.substring(0, 4))
      month = parseInt(fyEnd.substring(4, 6))
    } else {
      return fyEnd
    }

    // 12月決算（12月終了）以外は開始年は前年
    if (month < 12) {
      year -= 1
    }

    return `${year}年度`
  } catch {
    return fyEnd || '-'
  }
}

/**
 * 値の増減を判定
 */
export function getChangeIndicator(current: number | null, previous: number | null): 'up' | 'down' | 'neutral' {
  if (current === null || previous === null) return 'neutral'
  if (current > previous) return 'up'
  if (current < previous) return 'down'
  return 'neutral'
}
