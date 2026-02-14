import React from 'react'
import { cn, formatMillions, formatPercent } from '../lib/utils'
import { Download } from 'lucide-react'
import { getApiUrl } from '../lib/api'
import type { YearData, EdinetData } from '@/types'

interface FinancialTableProps {
  years: YearData[]
  edinetData?: Record<string, EdinetData[]>
  isLoading?: boolean
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
  // 貸借対照表（純資産はグラフで確認するため非表示）
  // { label: '純資産', key: 'eq', format: formatMillions, category: '貸借対照表' },
  // キャッシュフロー
  { label: '営業CF', key: 'cfo', format: formatMillions, category: 'キャッシュフロー' },
  { label: '投資CF', key: 'cfi', format: formatMillions, category: 'キャッシュフロー' },
  { label: 'FCF', key: 'fcf', format: formatMillions, category: 'キャッシュフロー' },
  // 財務指標
  { label: 'ROE', key: 'roe', format: formatPercent, category: '財務指標' },
  { label: 'EPS（調整値）', key: 'adjusted_eps', format: (v) => v?.toFixed(1) || '-', category: '財務指標' },
  { label: 'BPS（調整値）', key: 'adjusted_bps', format: (v) => v?.toFixed(1) || '-', category: '財務指標' },
  // 株価指標（グラフで確認するため非表示）
  // { label: '株価', key: 'price', format: (v) => v?.toLocaleString() + '円' || '-', category: '株価指標' },
  // { label: 'PER', key: 'per', format: formatRatio, category: '株価指標' },
  // { label: 'PBR', key: 'pbr', format: formatRatio, category: '株価指標' },
]

export function FinancialTable({ years, edinetData, isLoading }: FinancialTableProps) {
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
              {/* カテゴリーヘッダー (決算期の場合は省略) */}
              {category !== '決算期' && (
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
              )}
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
                      // 優先順：CalculatedData の CamelCase キー -> 既存のフラットキー
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
                      } else if (row.key === 'eq') {
                        value = calc?.Eq
                      } else if (row.key === 'payout_ratio') {
                        value = calc?.PayoutRatio
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
          {/* 半期報告書ダウンロード行 */}
          <tr className="border-t-2 border-border/80 bg-surface/30">
            <td className="sticky left-0 bg-card px-4 py-3 font-semibold text-foreground z-10">
              半期報告書
            </td>
            {sortedYears.map((year) => {
              const reports = edinetData?.[year.fy_end] || []
              // 四半期報告書 (140) または 半期報告書 (160) を探す
              const semiAnnualReport = reports.find((r: EdinetData) => r.docTypeCode === '140' || r.docTypeCode === '160')

              return (
                <td
                  key={`${year.fy_end}-semi-pdf`}
                  className="px-4 py-3 text-right"
                >
                  <div className="flex justify-end items-center h-8">
                    {semiAnnualReport ? (
                      <button
                        onClick={async (e) => {
                          e.stopPropagation()
                          try {
                            const apiUrl = getApiUrl(`/api/pdf/${semiAnnualReport.docID}`)
                            const response = await fetch(apiUrl)
                            if (!response.ok) return
                            const blob = await response.blob()
                            const url = window.URL.createObjectURL(blob)
                            const a = document.createElement('a')
                            a.style.display = 'none'
                            a.href = url
                            a.download = `${semiAnnualReport.docID}.pdf`
                            document.body.appendChild(a)
                            a.click()
                            window.URL.revokeObjectURL(url)
                            document.body.removeChild(a)
                          } catch (error) {
                            console.error('PDF download error:', error)
                          }
                        }}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-primary/10 text-primary hover:bg-primary/20 transition-colors text-xs font-medium"
                        title={`${semiAnnualReport.docType} (提出日: ${semiAnnualReport.submitDate})`}
                      >
                        <Download className="w-3.5 h-3.5" />
                        {semiAnnualReport.docID}
                      </button>
                    ) : isLoading ? (
                      <div className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-surface border border-dashed border-border text-foreground-muted text-xs animate-pulse">
                        <div className="w-3 h-3 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
                        検索中...
                      </div>
                    ) : null}
                  </div>
                </td>
              )
            })}
          </tr>
          {/* 有価証券報告書ダウンロード行 */}
          <tr className="border-t border-border/50 bg-surface/30">
            <td className="sticky left-0 bg-card px-4 py-3 font-semibold text-foreground z-10">
              有価証券報告書
            </td>
            {sortedYears.map((year) => {
              // fy_end (YYYYMMDD) をキーにして書類を探す
              const reports = edinetData?.[year.fy_end] || []
              // 確定した有報 (120) を優先
              const annualReport = reports.find((r: EdinetData) => r.docTypeCode === '120')

              return (
                <td
                  key={`${year.fy_end}-pdf`}
                  className="px-4 py-3 text-right"
                >
                  <div className="flex justify-end items-center h-8">
                    {annualReport ? (
                      <button
                        onClick={async (e) => {
                          e.stopPropagation()
                          try {
                            const apiUrl = getApiUrl(`/api/pdf/${annualReport.docID}`)
                            const response = await fetch(apiUrl)
                            if (!response.ok) return
                            const blob = await response.blob()
                            const url = window.URL.createObjectURL(blob)
                            const a = document.createElement('a')
                            a.style.display = 'none'
                            a.href = url
                            a.download = `${annualReport.docID}.pdf`
                            document.body.appendChild(a)
                            a.click()
                            window.URL.revokeObjectURL(url)
                            document.body.removeChild(a)
                          } catch (error) {
                            console.error('PDF download error:', error)
                          }
                        }}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-primary/10 text-primary hover:bg-primary/20 transition-colors text-xs font-medium"
                        title={`${annualReport.docType} (提出日: ${annualReport.submitDate})`}
                      >
                        <Download className="w-3.5 h-3.5" />
                        {annualReport.docID}
                      </button>
                    ) : isLoading ? (
                      <div className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-surface border border-dashed border-border text-foreground-muted text-xs animate-pulse">
                        <div className="w-3 h-3 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
                        検索中...
                      </div>
                    ) : null}
                  </div>
                </td>
              )
            })}
          </tr>
        </tbody>
      </table>
    </div>
  )
}
