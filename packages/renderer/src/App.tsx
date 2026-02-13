import { useState, useEffect, useRef } from 'react'
import { Sidebar } from '@/components/Sidebar'
import { TitleBar } from '@/components/TitleBar'
import { MainContent } from '@/components/MainContent'
import { SettingsPage } from '@/components/SettingsPage'
import { useTheme } from '@/hooks/useTheme'
import * as api from '@/lib/api'
import { getApiUrl } from '@/lib/api'
import type { AnalysisResult, HistoryItem } from '@/types'

// 共通ライブラリからインポートするため、ここでの定義は削除

function App() {
  const { theme } = useTheme()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [view, setView] = useState<'home' | 'settings'>('home')
  const [analysisResults, setAnalysisResults] = useState<AnalysisResult[]>([])
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analysisMessage, setAnalysisMessage] = useState('')
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const eventSourcesRef = useRef<Record<string, EventSource>>({})

  // テーマをHTMLに適用
  useEffect(() => {
    const root = document.documentElement
    if (theme === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
  }, [theme])

  // 左端検出でサイドバーを開く
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (e.clientX <= 80 && !sidebarOpen) {
        setSidebarOpen(true)
      }
    }
    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [sidebarOpen])

  // 起動時にAPIキーをバックエンドに送信し、完了後に履歴を取得
  useEffect(() => {
    const loadAndSyncSettings = async () => {
      try {
        let settings
        // Electron APIが利用可能な場合
        if (window.electronAPI?.getSettings) {
          settings = await window.electronAPI.getSettings()
        } else {
          // ローカルストレージから読み込む（Web版フォールバック）
          const stored = localStorage.getItem('mebuki-settings')
          if (stored) {
            settings = JSON.parse(stored)
          }
        }

        if (settings) {
          // FastAPIに設定を送信
          try {
            await api.updateSettings(settings)
          } catch (err) {
            console.error('バックエンドへの設定送信に失敗しました:', err)
          }
        }

        // 設定同期の後に履歴を取得（保存先パスが確定していることを確実にするため）
        fetchHistory()
      } catch (err) {
        console.error('設定の同期に失敗しました:', err)
        // 失敗しても履歴取得だけは試みる
        fetchHistory()
      }
    }

    loadAndSyncSettings()
  }, [])

  // メインプロセスからの遷移通知を監視
  useEffect(() => {
    if (window.electronAPI?.onNavigate) {
      window.electronAPI.onNavigate((target: string) => {
        if (target === 'settings') {
          setView('settings')
        }
      })
    }
  }, [])

  const fetchHistory = async () => {
    try {
      const response = await api.getHistory()
      setHistory(response.data || [])
    } catch (err) {
      console.error('履歴の取得に失敗しました:', err)
    }
  }

  const handleAnalyze = async (code: string, forceRefresh: boolean = false) => {
    // 進行中のすべての分析の接続を閉じる（幽霊タスク防止のため）
    Object.keys(eventSourcesRef.current).forEach(existingCode => {
      console.log(`Closing existing connection for [${existingCode}] before new analysis`);
      eventSourcesRef.current[existingCode].close();
      delete eventSourcesRef.current[existingCode];
    });

    setIsAnalyzing(true)
    setError(null)

    // 常に最新の1件のみを表示するように変更
    setAnalysisResults(() => {
      const newResult: AnalysisResult = {
        code,
        name: '取得中...',
        metrics: { years: [], analysis_years: 0 },
        analyzed_at: new Date().toISOString(),
        status: 'initializing',
        message: '準備中...'
      };
      return [newResult];
    });

    setAnalysisMessage('分析をしています...')

    try {
      // APIキーの有無を事前にチェック
      let settings;
      if (window.electronAPI?.getSettings) {
        settings = await window.electronAPI.getSettings();
      } else {
        const stored = localStorage.getItem('mebuki-settings');
        if (stored) settings = JSON.parse(stored);
      }

      if (!settings?.jquantsApiKey || !settings?.edinetApiKey) {
        setError('APIキーが設定されていません。右上の「設定」ボタンからJ-QuantsとEDINETのAPIキーを入力してください。');
        const remainingCount = Object.keys(eventSourcesRef.current).length;
        if (remainingCount === 0) {
          setIsAnalyzing(false);
        }
        return;
      }

      // セットアップ完了後に再度trueにする（他が完了してfalseになっている可能性があるため）
      setIsAnalyzing(true)

      // SSEで分析を実行（forceRefresh=trueの場合はキャッシュを無視）
      const url = forceRefresh
        ? getApiUrl(`/api/analyze/${code}/stream?force_refresh=true`)
        : getApiUrl(`/api/analyze/${code}/stream`)
      const eventSource = new EventSource(url)
      eventSourcesRef.current[code] = eventSource

      eventSource.onopen = () => {
        console.log(`SSE Connection Opened [${code}]`);
        // 接続が開いたらステータスを更新
        setAnalysisResults(prev => prev.map(r => {
          if (r.code === code && r.status === 'initializing') {
            return { ...r, message: '通信確立、分析開始...' };
          }
          return r;
        }));
      };

      eventSource.addEventListener('progress', (event) => {
        try {
          console.log(`SSE Progress Event Received [${code}]:`, event.data);
          const data = JSON.parse(event.data);
          updateAnalysisResultFromSSE(code, data);

          if (data.message) {
            setAnalysisMessage(`${data.company_name || code} の分析をしています`);
          }
        } catch (e) {
          console.error(`Error parsing progress data [${code}]:`, e);
        }
      });

      eventSource.addEventListener('complete', (event) => {
        try {
          console.log(`SSE Complete Event Received [${code}]:`, event.data);
          const data = JSON.parse(event.data);

          setAnalysisResults(prev => prev.map(r => {
            // 4ケタと5ケタの違いを許容
            const isMatch = r.code === code || (r.code.slice(0, 4) === code.slice(0, 4));
            if (isMatch) {
              const resultData = data.result || {};
              return {
                ...r, // 既存のステートをベースにする（万が一 backend の最終結果に一部データが欠けていても維持するため）
                ...resultData,
                code: r.code, // ID不整合を防ぐため
                status: 'complete',
                message: '分析完了'
              };
            }
            return r;
          }));
        } catch (e) {
          console.error(`Error parsing complete data [${code}]:`, e);
        }

        eventSource.close();
        delete eventSourcesRef.current[code];

        const remainingCount = Object.keys(eventSourcesRef.current).length;
        if (remainingCount === 0) {
          setIsAnalyzing(false);
        }

        fetchHistory();
      });

      eventSource.addEventListener('app-error', (event) => {
        try {
          const data = JSON.parse((event as MessageEvent).data)
          const errMsg = data.message || '分析中にエラーが発生しました'
          setError(`${code}: ${errMsg}`)

          setAnalysisResults(prev => prev.map(r => {
            if (r.code === code) {
              return { ...r, status: 'error', message: errMsg };
            }
            return r;
          }));
        } catch {
          setError(`${code}: 分析中にエラーが発生しました`)
        }

        eventSource.close();
        delete eventSourcesRef.current[code];
        const remainingCount = Object.keys(eventSourcesRef.current).length;
        if (remainingCount === 0) {
          setIsAnalyzing(false);
        }
      })

      eventSource.onerror = (e) => {
        console.error(`SSE Connection Error [${code}]`, e);

        // EventSourceは自動再接続を試みるため、readyStateを確認
        if (eventSource.readyState === EventSource.CLOSED) {
          if (eventSourcesRef.current[code]) {
            setError(`${code}: サーバーとの接続が終了しました。`)
            setAnalysisResults(prev => prev.map(r => {
              if (r.code === code && r.status !== 'complete') {
                return { ...r, status: 'error', message: '切断されました' };
              }
              return r;
            }));
            delete eventSourcesRef.current[code];
          }
        } else if (eventSource.readyState === EventSource.CONNECTING) {
          console.log(`SSE Reconnecting [${code}]...`);
          setAnalysisResults(prev => prev.map(r => {
            if (r.code === code && r.status !== 'complete') {
              return { ...r, message: '再接続中...' };
            }
            return r;
          }));
        }

        const remainingCount = Object.keys(eventSourcesRef.current).length;
        if (remainingCount === 0) {
          setIsAnalyzing(false);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '分析に失敗しました')
      setIsAnalyzing(false)
      delete eventSourcesRef.current[code];
    }
  }





  const updateAnalysisResultFromSSE = (code: string, sseData: any, isComplete = false) => {
    setAnalysisResults(prev => prev.map(r => {
      const isMatch = r.code === code || (r.code.slice(0, 4) === code.slice(0, 4));
      if (isMatch) {
        const partialData = sseData.data || sseData.result || {};
        return {
          ...r,
          ...partialData,
          code: r.code,
          status: isComplete ? 'complete' : (sseData.status || partialData.status || r.status),
          message: sseData.message || r.message,
          name: sseData.company_name || partialData.name || r.name,
          sector_33_name: partialData.sector_33_name || r.sector_33_name,
          market_name: partialData.market_name || r.market_name,
          edinet_data: partialData.edinet_data || r.edinet_data
        };
      }
      return r;
    }));
  }

  const handleCancel = () => {
    Object.keys(eventSourcesRef.current).forEach(code => {
      eventSourcesRef.current[code].close()
    })
    eventSourcesRef.current = {}
    setIsAnalyzing(false)
    setError(null)
    setAnalysisMessage('')
  }

  const handleHistorySelect = async (code: string) => {
    // 一覧から選択した場合は通常の分析を実行（キャッシュがあればキャッシュから読み込み）
    handleAnalyze(code)
    setSidebarOpen(false)
  }

  const handleReanalyze = async (code: string) => {
    // 最新情報で再分析（キャッシュを無視）
    handleAnalyze(code, true)
    setSidebarOpen(false)
  }

  const handleDelete = async (code: string) => {
    console.log(`handleDelete called for code: ${code}`);
    try {
      await api.clearCache(code)
      console.log('Delete successful, fetching new history...');
      // 一覧を更新
      fetchHistory();
      // 現在表示中の結果が削除対象の場合はクリア
      setAnalysisResults(prev => prev.filter(r => r.code !== code));
    } catch (err) {
      console.error('キャッシュの削除に失敗しました:', err);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-background text-foreground">
      <TitleBar
        onSearch={handleAnalyze}
        onSettingsClick={() => setView('settings')}
        onHomeClick={() => setView('home')}
        isAnalyzing={isAnalyzing}
        analysisMessage={analysisMessage}
        onCancel={handleCancel}
        showSearch={view === 'home'}
      />

      {/* メインエリア */}
      <div className="flex flex-1 overflow-hidden relative pt-[48px]">
        {view === 'home' ? (
          <>
            {/* サイドバー */}
            <Sidebar
              isOpen={sidebarOpen}
              onClose={() => setSidebarOpen(false)}
              onHistorySelect={handleHistorySelect}
              onDelete={handleDelete}
              onReanalyze={handleReanalyze}
              history={history}
              isAnalyzing={isAnalyzing}
            />

            {/* メインコンテンツ */}
            <MainContent
              results={analysisResults}
              isAnalyzing={isAnalyzing}
              error={error}
              sidebarOpen={sidebarOpen}
              onCancel={handleCancel}
            />
          </>
        ) : (
          <SettingsPage />
        )}
      </div>
    </div>
  )
}

export default App
