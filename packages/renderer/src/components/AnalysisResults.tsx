import { useState } from 'react'
import { Building2, TrendingUp, Table, BarChart3 } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { FinancialTable } from '@/components/FinancialTable'
import { FinancialCharts, CHART_TABS, type ChartTab } from '@/components/FinancialCharts'
import { FinancialMetricTable } from '@/components/FinancialMetricTable'
import { formatDate, cn } from '../lib/utils'
import type { AnalysisResult } from '@/types'
import { Button } from '@/components/ui/Button'

interface AnalysisResultsProps {
  result: AnalysisResult
  isAnalyzing?: boolean
}

type TabType = 'data' | 'graph'

export function AnalysisResults({
  result,
  isAnalyzing,
}: AnalysisResultsProps) {
  const [activeTab, setActiveTab] = useState<TabType>('data')
  const [graphTab, setGraphTab] = useState<ChartTab>('cashflow')

  return (
    <div className="space-y-6">
      {/* 銘柄情報カード (Sticky Header) */}
      <div className="sticky top-0 z-20 pb-2 bg-background/80 backdrop-blur-sm -mx-2 px-2">
        <Card className="p-4 shadow-md border-brand-start/20">
          <div className="grid grid-cols-1 md:grid-cols-3 items-center gap-4">
            {/* 左: 銘柄情報 */}
            <div className="space-y-1 min-w-0">
              <div className="flex items-center gap-3">
                <h2 className="text-xl font-bold text-foreground">
                  <span className="text-mebuki-brand font-mono mr-2">{result.code.slice(0, 4)}</span>
                  {result.name}
                </h2>
              </div>

              <div className="flex items-center gap-4 text-xs text-foreground-muted">
                {result.sector_33_name && (
                  <span className="flex items-center gap-1">
                    <Building2 className="w-3.5 h-3.5" />
                    {result.sector_33_name}
                  </span>
                )}
                {result.market_name && (
                  <span className="flex items-center gap-1">
                    <TrendingUp className="w-3.5 h-3.5" />
                    {result.market_name}
                  </span>
                )}
              </div>
            </div>

            {/* 中央: 最新年度末株価 */}
            <div className="flex flex-col items-center justify-center py-1 px-4 min-h-[56px]">
              {(() => {
                const latestYear = result.metrics?.years?.[0];
                const price = latestYear?.CalculatedData?.Price ?? latestYear?.price;
                const fyEnd = latestYear?.fy_end;
                const formattedDate = fyEnd ? (
                  fyEnd.length === 8
                    ? `${fyEnd.slice(0, 4)}年${fyEnd.slice(4, 6)}月${fyEnd.slice(6, 8)}日`
                    : fyEnd.length === 10
                      ? `${fyEnd.slice(0, 4)}年${fyEnd.slice(5, 7)}月${fyEnd.slice(8, 10)}日`
                      : fyEnd
                ) : null;

                if (price !== undefined && price !== null) {
                  return (
                    <div className="flex flex-col items-center">
                      <div className="flex items-baseline gap-2">
                        <span className="text-xl font-bold text-foreground-muted">株価</span>
                        <span className="text-2xl font-bold text-mebuki-brand tabular-nums">
                          ¥{price.toLocaleString()}
                        </span>
                      </div>
                      <div className="text-[10px] text-foreground-muted mt-0.5">
                        {formattedDate} 終値
                      </div>
                    </div>
                  );
                } else if (isAnalyzing) {
                  return (
                    <div className="flex items-center gap-2 text-foreground-muted">
                      <div className="w-1.5 h-1.5 bg-mebuki-brand rounded-full animate-pulse" />
                      <span className="text-xs font-medium">株価を取得中...</span>
                    </div>
                  );
                } else {
                  return <span className="text-xs text-foreground-muted">---</span>;
                }
              })()}
            </div>

            {/* 右: タブ切り替えボタン */}
            <div className="flex justify-end">
              <div className="flex items-center bg-surface border border-border rounded-lg p-1">
                <TabButton
                  active={activeTab === 'data'}
                  onClick={() => setActiveTab('data')}
                  icon={<Table className="w-4 h-4" />}
                  label="データ"
                />
                <TabButton
                  active={activeTab === 'graph'}
                  onClick={() => setActiveTab('graph')}
                  icon={<BarChart3 className="w-4 h-4" />}
                  label="グラフ"
                />

              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* 1ページ1カード形式の表示エリア */}
      <div className="">
        {activeTab === 'data' && (
          <Card className="p-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <h3 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
              <Table className="w-5 h-5 text-mebuki-brand" />
              年度別財務データ
            </h3>
            {result.metrics?.years && result.metrics.years.length > 0 ? (
              <FinancialTable
                years={result.metrics.years}
              />
            ) : isAnalyzing ? (
              <LoadingState message="財務データを取得中..." />
            ) : (
              <EmptyState message="財務データが見つかりませんでした" />
            )}
          </Card>
        )}

        {activeTab === 'graph' && (
          <Card className="p-6 animate-in fade-in slide-in-from-bottom-2 duration-300 overflow-hidden">
            <div className="flex flex-col space-y-6">
              {/* グラフカテゴリータブ */}
              <div className="flex gap-2 border-b border-border pb-2 overflow-x-auto scrollbar-hide">
                {CHART_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setGraphTab(tab.id)}
                    className={cn(
                      'px-4 py-2 text-sm font-medium rounded-md transition-colors whitespace-nowrap flex-shrink-0',
                      graphTab === tab.id
                        ? 'bg-mebuki-brand text-white shadow-sm'
                        : 'text-foreground-muted hover:bg-surface hover:text-foreground'
                    )}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* コンテンツエリア: 左グラフ、右表 */}
              <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
                <div className="lg:col-span-2">
                  {result.metrics?.years && result.metrics.years.length > 0 ? (
                    <FinancialCharts
                      years={result.metrics.years}
                      activeTab={graphTab}
                    />
                  ) : isAnalyzing ? (
                    <LoadingState message="グラフデータを準備中..." />
                  ) : (
                    <EmptyState message="表示可能なグラフデータがありません" />
                  )}
                </div>

                <div className="lg:col-span-3 border-l border-border/50 pl-6 overflow-hidden">
                  <div className="h-full flex flex-col">
                    <h4 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                      <Table className="w-4 h-4 text-mebuki-brand" />
                      主要指標推移
                    </h4>
                    {result.metrics?.years && result.metrics.years.length > 0 ? (
                      <FinancialMetricTable
                        years={result.metrics.years}
                        activeTab={graphTab}
                      />
                    ) : (
                      <div className="flex items-center justify-center h-40 border border-dashed border-border rounded-lg text-xs text-foreground-muted">
                        データがありません
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </Card>
        )}
      </div>


      <div className="text-center pb-6">
        <p className="text-xs text-foreground-muted">
          最終分析日: {formatDate(result.analyzed_at)}
        </p>
      </div>
    </div>
  )
}

function TabButton({ active, onClick, icon, label }: { active: boolean, onClick: () => void, icon: React.ReactNode, label: string }) {
  return (
    <Button
      variant={active ? 'default' : 'ghost'}
      size="sm"
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 px-4 h-8 transition-all",
        active ? "bg-mebuki-brand text-white shadow-sm" : "text-foreground-muted hover:text-foreground"
      )}
    >
      {icon}
      <span className="font-medium">{label}</span>
    </Button>
  )
}

function LoadingState({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center py-20 border border-dashed border-border rounded-lg">
      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-mebuki-brand mr-3"></div>
      <p className="text-sm text-foreground-muted">{message}</p>
    </div>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 border border-dashed border-border rounded-lg">
      <p className="text-sm text-foreground-muted">{message}</p>
    </div>
  )
}
