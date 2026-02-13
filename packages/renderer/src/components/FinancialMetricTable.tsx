import { cn, formatMillions, formatPercent } from '@/lib/utils'
import type { YearData } from '@/types'

interface FinancialMetricTableProps {
    years: YearData[]
    activeTab: 'cashflow' | 'efficiency' | 'allocation' | 'valuation'
}

interface MetricRow {
    label: string
    key: string
    format: (value: any) => string
    unit?: string
}

const metricConfigs: Record<string, MetricRow[]> = {
    cashflow: [
        { label: '営業CF', key: 'CFO', format: formatMillions, unit: '（百万円）' },
        { label: '投資CF', key: 'CFI', format: formatMillions, unit: '（百万円）' },
        { label: 'FCF', key: 'CFC', format: formatMillions, unit: '（百万円）' },
        { label: '現預金等', key: 'CashEq', format: formatMillions, unit: '（百万円）' },
    ],
    efficiency: [
        { label: 'CF変換率', key: 'CFCVR', format: formatPercent },
        { label: '簡易ROIC', key: 'SimpleROIC', format: formatPercent },
        { label: 'ROE', key: 'ROE', format: formatPercent },
    ],
    allocation: [
        { label: 'BPS', key: 'AdjustedBPS', format: (v) => v?.toFixed(1) || '-', unit: '（円）' },
        { label: 'EPS', key: 'AdjustedEPS', format: (v) => v?.toFixed(1) || '-', unit: '（円）' },
        { label: '配当性向', key: 'PayoutRatio', format: formatPercent },
    ],
    valuation: [
        { label: '株価', key: 'Price', format: (v) => v?.toLocaleString() || '-', unit: '（円）' },
        { label: 'PBR', key: 'PBR', format: (v) => v?.toFixed(2) || '-', unit: '（倍）' },
        { label: 'PER', key: 'PER', format: (v) => v?.toFixed(2) || '-', unit: '（倍）' },
    ],
}

export function FinancialMetricTable({ years, activeTab }: FinancialMetricTableProps) {
    const sortedYears = [...years].reverse()
    const rows = metricConfigs[activeTab] || []

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-sm">
                <thead>
                    <tr className="border-b border-border">
                        <th className="px-3 py-2 text-left font-medium text-foreground-muted">指標</th>
                        {sortedYears.map((year) => (
                            <th key={year.fy_end} className="px-3 py-2 text-right font-medium text-foreground-muted whitespace-nowrap">
                                {year.CalculatedData?.FinancialPeriod ?? year.financial_period}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.map((row) => (
                        <tr key={row.key} className="border-b border-border/50 hover:bg-surface/30 transition-colors">
                            <td className="px-3 py-2 font-medium text-foreground">
                                <div className="flex flex-col">
                                    <span>{row.label}</span>
                                    {row.unit && <span className="text-[10px] text-foreground-muted font-normal">{row.unit}</span>}
                                </div>
                            </td>
                            {sortedYears.map((year) => {
                                const value = year.CalculatedData?.[row.key as keyof typeof year.CalculatedData]
                                const isNegative = typeof value === 'number' && value < 0
                                return (
                                    <td
                                        key={`${year.fy_end}-${row.key}`}
                                        className={cn(
                                            'px-3 py-2 text-right tabular-nums align-bottom',
                                            isNegative ? 'text-error' : 'text-foreground'
                                        )}
                                    >
                                        {row.format(value)}
                                    </td>
                                )
                            })}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    )
}
