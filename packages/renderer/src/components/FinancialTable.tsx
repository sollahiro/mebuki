import React from 'react'
import { cn, formatMillions, formatPercent } from '../lib/utils'
import type { YearData } from '@/types'

interface FinancialTableProps {
  years: YearData[]
}

interface TableRow {
  label: string
  key: keyof YearData
  format: (value: any) => string
  category: string
}

const tableRows: TableRow[] = [
  // 損益計算書
  { label: '売上高', key: 'sales', format: formatMillions, category: '損益計算書' },
  { label: '営業利益', key: 'op', format: formatMillions, category: '損益計算書' },
  { label: '当期純利益', key: 'np', format: formatMillions, category: '損益計算書' },
  // キャッシュフロー
  { label: '営業CF', key: 'cfo', format: formatMillions, category: 'キャッシュフロー' },
  { label: '投資CF', key: 'cfi', format: formatMillions, category: 'キャッシュフロー' },
  { label: 'FCF', key: 'fcf', format: formatMillions, category: 'キャッシュフロー' },
  // 財務指標
  { label: 'ROE', key: 'roe', format: formatPercent, category: '財務指標' },
  { label: 'EPS（調整値）', key: 'adjusted_eps', format: (v) => v?.toFixed(1) || '-', category: '財務指標' },
  { label: 'BPS（調整値）', key: 'adjusted_bps', format: (v) => v?.toFixed(1) || '-', category: '財務指標' },
]

export function FinancialTable({ years }: FinancialTableProps) {
  // 年度を古い順にソート
  const sortedYears = [...years].reverse()

  // カテゴリーでグループ化
  const categories = [...new Set(tableRows.map((r) => r.category))]

  return (
    <div className="overflow-x-auto scrollbar-thin">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="sticky left-0 bg-surface px-4 py-3 text-left font-medium text-foreground-muted z-10">
              指標
            </th>
            {sortedYears.map((year) => (
              <th
                key={year.fy_end}
                className="px-4 py-3 text-right font-medium text-foreground-muted min-w-[100px]"
              >
                {year.CalculatedData?.FinancialPeriod ?? year.financial_period}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {categories.map((category) => (
            <React.Fragment key={`cat-group-${category}`}>
              {/* カテゴリーヘッダー */}
              <tr key={`cat-${category}`} className="bg-surface/50">
                <td
                  colSpan={sortedYears.length + 1}
                  className="px-4 py-2 text-xs font-semibold text-foreground-muted uppercase tracking-wider"
                >
                  {category}
                  {['損益計算書', '貸借対照表', 'キャッシュフロー'].includes(category) && (
                    <span className="ml-2 font-normal normal-case">（百万円）</span>
                  )}
                </td>
              </tr>
              {/* カテゴリーの行 */}
              {tableRows
                .filter((row) => row.category === category)
                .map((row) => (
                  <tr
                    key={row.key}
                    className={cn(
                      'border-b border-border/50 hover:bg-surface/50 transition-colors',
                    )}
                  >
                    <td className="sticky left-0 bg-card px-4 py-3 font-medium text-foreground z-10">
                      {row.label}
                    </td>
                    {sortedYears.map((year) => {
                      let value: number | null | undefined
                      const calc = year.CalculatedData

                      if (row.key === 'adjusted_eps') {
                        value = calc?.AdjustedEPS ?? year.eps
                      } else if (row.key === 'adjusted_bps') {
                        value = calc?.AdjustedBPS ?? year.bps
                      } else if (row.key === 'sales') {
                        value = calc?.Sales
                      } else if (row.key === 'op') {
                        value = calc?.OP
                      } else if (row.key === 'np') {
                        value = calc?.NP
                      } else if (row.key === 'cfo') {
                        value = calc?.CFO
                      } else if (row.key === 'cfi') {
                        value = calc?.CFI
                      } else if (row.key === 'fcf') {
                        value = calc?.CFC
                      } else if (row.key === 'roe') {
                        value = calc?.ROE
                      } else {
                        value = (calc?.[row.key as keyof typeof calc] ?? year[row.key as keyof typeof year]) as number | null | undefined
                      }
                      const isNegative = typeof value === 'number' && value < 0

                      return (
                        <td
                          key={`${year.fy_end}-${row.key}`}
                          className={cn(
                            'px-4 py-3 text-right tabular-nums',
                            isNegative ? 'text-error' : 'text-foreground'
                          )}
                        >
                          {row.format(value)}
                        </td>
                      )
                    })}
                  </tr>
                ))}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  )
}
