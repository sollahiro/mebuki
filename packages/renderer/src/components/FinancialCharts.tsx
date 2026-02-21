import {
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ComposedChart,
} from 'recharts'
import type { YearData } from '@/types'
import { useTheme } from '@/hooks/useTheme'

interface FinancialChartsProps {
  years: YearData[]
}

// グラフタイプをエクスポート
export type ChartTab = 'cashflow' | 'efficiency' | 'allocation' | 'valuation'

export const CHART_TABS: { id: ChartTab; label: string }[] = [
  { id: 'cashflow', label: '稼ぐ・蓄える' },
  { id: 'efficiency', label: '収益性' },
  { id: 'allocation', label: '還元・蓄積' },
  { id: 'valuation', label: '評価' },
]

interface FinancialChartsProps {
  years: YearData[]
  activeTab: ChartTab
}

// カスタムX軸ラベル（改行対応）
const CustomXAxisTick = ({ x, y, payload, color }: any) => {
  if (!payload || !payload.value) return null

  // 「YYYY年MM月期」を「YYYY年」と「MM月期」に分割
  const parts = payload.value.split('年')
  const year = parts[0] + '年'
  const period = parts[1] || ''

  return (
    <g transform={`translate(${x},${y})`}>
      <text
        x={0}
        y={0}
        dy={16}
        textAnchor="middle"
        fill={color}
        fontSize={12}
      >
        <tspan x={0} dy="1em">{year}</tspan>
        <tspan x={0} dy="1.2em">{period}</tspan>
      </text>
    </g>
  )
}

export function FinancialCharts({ years, activeTab }: FinancialChartsProps) {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  // テーマに基づいたスタイル定義
  const chartContainerStyle = "w-full min-h-[400px] h-[450px]"
  const gridColor = isDark ? "rgba(255, 255, 255, 0.1)" : "rgba(0, 0, 0, 0.1)"
  const axisColor = isDark ? "#94a3b8" : "#475569" // Slate 300 vs Slate 600
  const tooltipStyle = {
    backgroundColor: isDark ? '#1e293b' : '#ffffff',
    border: `1px solid ${isDark ? '#334155' : '#e5e7eb'}`,
    borderRadius: '8px',
    color: isDark ? '#f1f5f9' : '#374151',
  }
  const legendStyle = { color: isDark ? '#f1f5f9' : '#374151' }

  // グラフ用カラーパレット (Light vs Dark)
  const colors = {
    indigo: isDark ? "#818cf8" : "#4f46e5",
    deepIndigo: isDark ? "#6366f1" : "#4338ca",
    slate: isDark ? "#94a3b8" : "#64748b",
    rose: isDark ? "#f43f5e" : "#e11d48",
    emerald: isDark ? "#10b981" : "#059669",
    amber: isDark ? "#f59e0b" : "#d97706",
    lightSlate: isDark ? "#cbd5e1" : "#94a3b8",
  }

  // 年度を古い順にソート
  const sortedYears = [...years].reverse()

  // チャートデータを作成
  const chartData = sortedYears.map((year) => {
    const calc = year.CalculatedData
    return {
      year: calc?.FinancialPeriod ?? year.financial_period,
      sales: calc?.Sales ?? year.sales,
      op: calc?.OP ?? year.op,
      np: calc?.NP ?? year.np,
      cfo: calc?.CFO ?? year.cfo,
      cfi: calc?.CFI ?? year.cfi,
      fcf: calc?.CFC ?? year.fcf,
      roe: calc?.ROE ?? year.roe,
      eps: calc?.AdjustedEPS ?? year.eps,
      bps: calc?.AdjustedBPS ?? year.bps,
      price: calc?.Price ?? year.price,
      per: calc?.PER ?? year.per,
      pbr: calc?.PBR ?? year.pbr,
      simple_roic: calc?.SimpleROIC ?? (year.op && year.eq ? (year.op / year.eq * 100) : null),
      cf_conversion_rate: calc?.CFCVR ?? (year.cfo && year.op ? (year.cfo / year.op * 100) : null),
      payout_ratio: calc?.PayoutRatio ?? year.payout_ratio,
      cash_eq: calc?.CashEq ?? year.cash_eq,
    }
  })

  const renderChart = () => {
    switch (activeTab) {
      // グラフ1: 稼ぐ・蓄える (Cash Flow & Stock)
      // 左軸: 営業CF, 投資CF (並列棒) / FCF (線) / 現金及び現金同等物 (線)
      case 'cashflow':
        return (
          <div className={chartContainerStyle}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={true} horizontal={true} />
                <XAxis
                  dataKey="year"
                  stroke={axisColor}
                  interval={0}
                  tick={<CustomXAxisTick color={axisColor} />}
                  height={60}
                />
                <YAxis
                  stroke={axisColor}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value: number, name: string) => {
                    if (value === null || value === undefined) return ['-', name]
                    return [value.toLocaleString(), name]
                  }}
                />
                <Legend wrapperStyle={legendStyle} />
                <Bar
                  dataKey="cfo"
                  name="営業CF"
                  fill={colors.indigo}
                  radius={[4, 4, 0, 0]}
                />
                <Bar
                  dataKey="cfi"
                  name="投資CF"
                  fill={colors.slate}
                  radius={[4, 4, 0, 0]}
                />
                <Line
                  type="monotone"
                  dataKey="fcf"
                  name="FCF"
                  stroke={colors.deepIndigo}
                  strokeWidth={3}
                  dot={{ fill: colors.deepIndigo, r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="cash_eq"
                  name="現預金等"
                  stroke={colors.rose}
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={{ fill: colors.rose, r: 3 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
            <p className="text-[10px] text-foreground-muted mt-2 text-center">
              ※ フロー(CF)とストック(残高)の対比
            </p>
          </div>
        )

      // グラフ2: 収益性 (Capital Efficiency)
      // 左軸: CF変換率 (線)
      // 右軸: ROE (線), 簡易ROIC (線)
      case 'efficiency':
        return (
          <div className={chartContainerStyle}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={true} horizontal={true} />
                <XAxis
                  dataKey="year"
                  stroke={axisColor}
                  interval={0}
                  tick={<CustomXAxisTick color={axisColor} />}
                  height={60}
                />
                <YAxis
                  yAxisId="left"
                  stroke={axisColor}
                  label={{ value: '%', angle: -90, position: 'insideLeft', style: { fill: axisColor, fontSize: 11 } }}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  stroke={axisColor}
                  label={{ value: '%', angle: 90, position: 'insideRight', style: { fill: axisColor, fontSize: 11 } }}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value: number, name: string) => {
                    if (value === null || value === undefined) return ['-', name]
                    return [value.toFixed(1) + '%', name]
                  }}
                />
                <Legend wrapperStyle={legendStyle} />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="cf_conversion_rate"
                  name="CF変換率"
                  stroke={colors.indigo}
                  strokeWidth={2}
                  dot={{ fill: colors.indigo, r: 3 }}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="simple_roic"
                  name="簡易ROIC"
                  stroke={colors.emerald}
                  strokeWidth={4}
                  dot={{ fill: colors.emerald, r: 5 }}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="roe"
                  name="ROE"
                  stroke={colors.amber}
                  strokeWidth={3}
                  dot={{ fill: colors.amber, r: 4 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
            <p className="text-[10px] text-foreground-muted mt-2 text-center">
              ※ 簡易ROIC = 営業利益 / 純資産、CF変換率 = 営業CF / 営業利益
            </p>
          </div>
        )

      // グラフ3: 還元・蓄積 (Allocation)
      // 左軸: BPS (棒), EPS (線)
      // 右軸: 配当性向 (線)
      case 'allocation':
        return (
          <div className={chartContainerStyle}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} barGap={4} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={true} horizontal={true} />
                <XAxis
                  dataKey="year"
                  stroke={axisColor}
                  interval={0}
                  tick={<CustomXAxisTick color={axisColor} />}
                  height={60}
                />
                <YAxis
                  yAxisId="left"
                  stroke={axisColor}
                  label={{ value: '円', angle: -90, position: 'insideLeft', style: { fill: axisColor, fontSize: 11 } }}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  stroke={axisColor}
                  label={{ value: '%', angle: 90, position: 'insideRight', style: { fill: axisColor, fontSize: 11 } }}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value: number, name: string) => {
                    if (value === null || value === undefined) return ['-', name]
                    if (name === '配当性向') return [value.toFixed(1) + '%', name]
                    return [value.toFixed(1) + '円', name]
                  }}
                />
                <Legend wrapperStyle={legendStyle} />
                <Bar
                  yAxisId="left"
                  dataKey="bps"
                  name="BPS"
                  fill={colors.lightSlate}
                  radius={[4, 4, 0, 0]}
                  barSize={32}
                />
                <Bar
                  yAxisId="left"
                  dataKey="eps"
                  name="EPS"
                  fill={colors.indigo}
                  radius={[4, 4, 0, 0]}
                  barSize={32}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="payout_ratio"
                  name="配当性向"
                  stroke={colors.amber}
                  strokeWidth={3}
                  dot={{ fill: colors.amber, r: 4 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
            <p className="text-[10px] text-foreground-muted mt-2 text-center">
              ※ 稼ぎ(EPS)が資産(BPS)に変わる過程を可視化
            </p>
          </div>
        )

      // グラフ4: 評価 (Market Valuation)
      // 左軸: 株価 (線)
      // 右軸: PBR, PER (線)
      case 'valuation':
        return (
          <div className={chartContainerStyle}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={true} horizontal={true} />
                <XAxis
                  dataKey="year"
                  stroke={axisColor}
                  interval={0}
                  tick={<CustomXAxisTick color={axisColor} />}
                  height={60}
                />
                <YAxis
                  yAxisId="left"
                  stroke={axisColor}
                  label={{ value: '円', angle: -90, position: 'insideLeft', style: { fill: axisColor, fontSize: 11 } }}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  stroke={axisColor}
                  label={{ value: '倍', angle: 90, position: 'insideRight', style: { fill: axisColor, fontSize: 11 } }}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value: number, name: string) => {
                    if (value === null || value === undefined) return ['-', name]
                    if (name === '株価') return [value.toLocaleString() + '円', name]
                    return [value.toFixed(2) + '倍', name]
                  }}
                />
                <Legend wrapperStyle={legendStyle} />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="price"
                  name="株価"
                  stroke={colors.emerald}
                  strokeWidth={3}
                  dot={{ fill: colors.emerald, r: 4 }}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="pbr"
                  name="PBR"
                  stroke={colors.indigo}
                  strokeWidth={2}
                  dot={{ fill: colors.indigo, r: 3 }}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="per"
                  name="PER"
                  stroke={colors.amber}
                  strokeWidth={3}
                  dot={{ fill: colors.amber, r: 4 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
            <p className="text-[10px] text-foreground-muted mt-2 text-center">
              ※ 市場評価指標の推移
            </p>
          </div>
        )

      default:
        return null
    }
  }

  return (
    <div className="w-full h-full min-h-[420px]">
      {renderChart()}
    </div>
  )
}
