import React, { useState, useEffect } from 'react'
import { useApp } from '@modelcontextprotocol/ext-apps/react'
import { Building2, Globe } from 'lucide-react'
import { FinancialTable } from './components/FinancialTable'
import { FinancialCharts, ChartTab, CHART_TABS } from './components/FinancialCharts'
import './index.css'

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
                const receivedData = source.status === 'ok' ? source.data : (source.data || source)

                console.log('McpApp: Processed data', receivedData)
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
        if (data) return;

        const timer = setTimeout(async () => {
            if (data) return;

            const params = new URLSearchParams(window.location.search)
            const code = params.get('code')

            if (code) {
                console.log(`McpApp: Triggering manual fallback for code ${code}`)
                try {
                    const response = await fetch(`http://localhost:8765/api/mcp/financial_history/${code}`)
                    const result = await response.json()
                    if (result.status === 'ok') {
                        setData(result.data)
                        setLoading(false)

                        // If it's a fallback, we check the URL for mode too
                        const isTable = window.location.pathname.includes('table') || params.get('mode') === 'table'
                        if (isTable) setMode('table')
                        else setMode('charts')
                    }
                } catch (err) {
                    console.error('McpApp: Manual fallback fetch failed', err)
                }
            }
        }, 2000)

        return () => clearTimeout(timer)
    }, [data])

    if (error) {
        return (
            <div className="flex items-center justify-center h-screen bg-background text-red-500 p-4">
                <div className="text-center">
                    <h2 className="text-lg font-bold mb-2">Connection Error</h2>
                    <p className="text-sm">{error.message}</p>
                </div>
            </div>
        )
    }

    if (!data && loading) {
        return (
            <div className="flex items-center justify-center h-screen bg-background text-foreground">
                <div className="flex flex-col items-center gap-4">
                    <div className="w-8 h-8 rounded-full border-4 border-primary/30 border-t-primary animate-spin" />
                    <p className="text-sm font-medium animate-pulse">データを読み込み中...</p>
                </div>
            </div>
        )
    }

    // Default to some basic info if data is missing (should not happen if loading finishes)
    const stockInfo = data?.company_info || {
        code: data?.code || "Unknown",
        name: data?.name || "",
        industry: data?.industry || data?.sector_33_name || "",
        market: data?.market || data?.market_name || ""
    }

    return (
        <div className="min-h-screen bg-background text-foreground p-4 flex flex-col gap-6">
            <header className="flex flex-col gap-3 border-b border-border pb-4">
                <div className="flex items-center justify-between">
                    <div className="flex flex-col gap-1.5">
                        <h1 className="text-2xl font-bold flex items-center gap-2">
                            <span className="text-foreground-muted/50 font-medium tracking-tight">{stockInfo.code}</span>
                            <span>{stockInfo.name}</span>
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
                                ? 'bg-primary text-primary-foreground shadow-md'
                                : 'text-foreground-muted hover:text-foreground'
                                }`}
                        >
                            詳細テーブル
                        </button>
                        <button
                            onClick={() => setMode('charts')}
                            className={`px-4 py-2 rounded-md text-sm font-bold transition-all ${mode === 'charts'
                                ? 'bg-primary text-primary-foreground shadow-md'
                                : 'text-foreground-muted hover:text-foreground'
                                }`}
                        >
                            分析グラフ
                        </button>
                    </div>
                </div>
            </header>

            <main className="flex-1 overflow-hidden">
                {mode === 'table' ? (
                    <div className="bg-card rounded-xl border border-border overflow-hidden shadow-sm">
                        <FinancialTable years={data?.metrics?.years || data?.history || []} />
                    </div>
                ) : (
                    <div className="flex flex-col gap-4">
                        <div className="flex gap-2">
                            {CHART_TABS.map((tab) => (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id)}
                                    className={`px-5 py-2 rounded-full text-xs font-bold transition-all ${activeTab === tab.id
                                        ? 'bg-primary text-primary-foreground shadow-lg shadow-primary/20'
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
    )
}

export default McpApp
