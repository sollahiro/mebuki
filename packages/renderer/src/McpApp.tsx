import React, { useState, useEffect } from 'react'
import { useApp } from '@modelcontextprotocol/ext-apps/react'
import { Building2, Globe } from 'lucide-react'
import { FinancialTable } from './components/FinancialTable'
import { FinancialCharts, ChartTab, CHART_TABS } from './components/FinancialCharts'
import { getApiUrl } from './lib/api'

/**
 * MCP App Component
 * 
 * Official standard for MCP Interactive UI (External Apps).
 * Uses @modelcontextprotocol/ext-apps SDK to handle handshakes and data delivery.
 */
const McpApp: React.FC = () => {
    const [data, setData] = useState<any>(null)
    const [mode, setMode] = useState<'table' | 'charts'>('charts')
    const [activeTab, setActiveTab] = useState<ChartTab>('cashflow')
    const [loading, setLoading] = useState(true)
    const [errorMessage, setErrorMessage] = useState<string | null>(null)

    // useApp handles the specialized handshake with the host (e.g. Claude)
    const { error } = useApp({
        appInfo: { name: "mebuki-financial-analyzer", version: "1.1.0" },
        capabilities: {}, // Required property
        onAppCreated: (appInstance) => {
            console.log('McpApp: Official SDK Connected')

            // This is the standard way to receive data when a tool is called
            appInstance.ontoolresult = async (result: any) => {
                console.log('McpApp: Received ontoolresult via SDK', result)
                setLoading(false)

                // Prioritize structuredContent (SEP-1865 standard)
                // Result can be nested depending on how the server returns it
                const source = result.structuredContent || result.data || result

                if (source.status === 'error') {
                    setErrorMessage(source.message || 'データ取得中にエラーが発生しました')
                    return
                }

                const receivedData = source.status === 'ok' ? source.data : (source.data || source)

                console.log('McpApp: Processed data object:', JSON.stringify(receivedData, null, 2))
                setData(receivedData)

                if (receivedData.mode === 'table' || receivedData.mode === 'charts') {
                    setMode(receivedData.mode)
                }
            }

            appInstance.onerror = (err) => console.error('McpApp SDK Error:', err)
        }
    })

    // Manual Fallback: In case the host's data push (ontoolresult) fails or is slow
    useEffect(() => {
        if (data || errorMessage) return;

        const timer = setTimeout(async () => {
            if (data || errorMessage) return;

            const params = new URLSearchParams(window.location.search)
            const code = params.get('code')

            if (code) {
                console.log(`McpApp: Triggering manual fallback for code ${code}`)
                try {
                    const apiUrl = getApiUrl(`/api/mcp/financial_history/${code}`)
                    const response = await fetch(apiUrl)
                    const result = await response.json()
                    if (result.status === 'ok') {
                        console.log('McpApp: Fallback Success', result.data)
                        setData(result.data)
                        setLoading(false)

                        // If it's a fallback, we check the URL for mode too
                        const isTable = window.location.pathname.includes('table') || params.get('mode') === 'table'
                        if (isTable) setMode('table')
                        else setMode('charts')
                    } else if (result.status === 'error') {
                        setErrorMessage(result.message)
                        setLoading(false)
                    }
                } catch (err) {
                    console.error('McpApp: Fallback fetch failed', err)
                    // If even fallback fails, we wait for SDK or show nothing
                }
            }
        }, 2000)

        return () => clearTimeout(timer)
    }, [data, errorMessage])

    if (error) {
        return (
            <div className="flex items-center justify-center min-h-screen p-4 text-destructive bg-background">
                <div className="text-center">
                    <h1 className="text-xl font-bold mb-2">MCP Connection Error</h1>
                    <p>{error.message}</p>
                </div>
            </div>
        )
    }

    if (errorMessage) {
        return (
            <div className="flex items-center justify-center min-h-screen p-4 bg-background">
                <div className="max-w-m w-full bg-destructive/10 border border-destructive/20 rounded-xl p-6 text-center">
                    <h1 className="text-xl font-bold text-destructive mb-2">エラーが発生しました</h1>
                    <p className="text-muted-foreground">{errorMessage}</p>
                    <button
                        onClick={() => window.location.reload()}
                        className="mt-4 px-4 py-2 bg-destructive text-destructive-foreground rounded-lg hover:bg-destructive/90 transition-colors"
                    >
                        再読み込み
                    </button>
                </div>
            </div>
        )
    }

    if (loading && !data) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-background p-4">
                <div className="flex flex-col items-center gap-12">
                    <div className="relative w-16 h-16 flex items-center justify-center">
                        {/* Ripple Circles */}
                        <div className="absolute inset-0 rounded-full bg-mebuki-brand opacity-20 animate-ripple" style={{ animationDelay: '0s' }} />
                        <div className="absolute inset-0 rounded-full bg-mebuki-brand opacity-20 animate-ripple" style={{ animationDelay: '1s' }} />
                        <div className="absolute inset-0 rounded-full bg-mebuki-brand opacity-20 animate-ripple" style={{ animationDelay: '2s' }} />

                        {/* Center Core */}
                        <div className="w-10 h-10 rounded-full bg-mebuki-brand shadow-lg z-10 flex items-center justify-center">
                            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        </div>
                    </div>
                    <div className="space-y-2 text-center">
                        <p className="text-lg font-bold tracking-tight text-mebuki-brand animate-pulse">データを分析中</p>
                        <p className="text-sm text-foreground-muted">財務構造を解析しています...</p>
                    </div>
                </div>
            </div>
        )
    }

    // Default to some basic info if data is missing (should not happen if loading finishes)
    // Try both lowerCase and CamelCase mapping
    const stockInfo = {
        code: data?.code || data?.Code || "Unknown",
        name: data?.name || data?.CompanyName || data?.CoName || "",
        industry: data?.industry || data?.sector_33_name || data?.Sector33CodeName || data?.S33Nm || "",
        market: data?.market || data?.market_name || data?.MarketName || data?.MktNm || ""
    }

    return (
        <div className="min-h-screen bg-background text-foreground flex flex-col items-center">
            <div className="max-w-5xl w-full p-4 flex flex-col gap-6">
                <header className="flex flex-col gap-3 border-b border-border pb-4">
                    <div className="flex items-center justify-between">
                        <div className="flex flex-col gap-1.5 focus:outline-none" tabIndex={0}>
                            <h1 className="text-2xl font-extrabold flex items-center gap-3">
                                <span className="text-mebuki-brand font-mono tracking-tighter">{stockInfo.code}</span>
                                <span className="text-foreground tracking-tight">{stockInfo.name}</span>
                            </h1>
                            <div className="flex items-center gap-4 text-xs font-medium text-foreground-muted">
                                <span className="flex items-center gap-1.5">
                                    <Building2 className="w-3.5 h-3.5 opacity-60" />
                                    {stockInfo.industry}
                                </span>
                                <span className="flex items-center gap-1.5">
                                    <Globe className="w-3.5 h-3.5 opacity-60" />
                                    {stockInfo.market}
                                </span>
                            </div>
                        </div>
                        <div className="flex bg-surface rounded-lg p-1 border border-border/50 shadow-sm">
                            <button
                                onClick={() => setMode('table')}
                                className={`px-4 py-2 rounded-md text-sm font-bold transition-all ${mode === 'table'
                                    ? 'bg-mebuki-brand text-white shadow-md'
                                    : 'text-foreground-muted hover:text-foreground'
                                    }`}
                            >
                                詳細テーブル
                            </button>
                            <button
                                onClick={() => setMode('charts')}
                                className={`px-4 py-2 rounded-md text-sm font-bold transition-all ${mode === 'charts'
                                    ? 'bg-mebuki-brand text-white shadow-md'
                                    : 'text-foreground-muted hover:text-foreground'
                                    }`}
                            >
                                分析グラフ
                            </button>
                        </div>
                    </div>
                </header>

                <main className="flex-1">
                    {mode === 'table' ? (
                        <div className="bg-card rounded-xl border border-border overflow-hidden shadow-sm">
                            <FinancialTable
                                years={data?.metrics?.years || data?.history || []}
                            />
                        </div>
                    ) : (
                        <div className="bg-card rounded-xl border border-border p-6 shadow-sm flex flex-col gap-6">
                            <div className="flex gap-2 mb-2">
                                {CHART_TABS.map((tab) => (
                                    <button
                                        key={tab.id}
                                        onClick={() => setActiveTab(tab.id)}
                                        className={`px-5 py-2 rounded-full text-xs font-bold transition-all ${activeTab === tab.id
                                            ? 'bg-mebuki-brand text-white shadow-lg shadow-primary/20'
                                            : 'bg-surface text-foreground-muted hover:bg-surface/70 hover:text-foreground'}`}
                                    >
                                        {tab.label}
                                    </button>
                                ))}
                            </div>
                            <FinancialCharts years={data?.metrics?.years || data?.history || []} activeTab={activeTab} />
                        </div>
                    )}
                </main>
            </div>
        </div>
    )
}

export default McpApp
