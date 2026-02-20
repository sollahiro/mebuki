import { useState, useEffect, useCallback, useRef } from 'react'
import { Eye, EyeOff, AlertCircle, CheckCircle, ExternalLink, Loader2, MessageSquare, Sparkles, ArrowRight } from 'lucide-react'
import { cn } from '../lib/utils'
import { getApiUrl } from '../lib/api'
import claudeIcon from '@/assets/claude-inverted.svg'
import gooseIcon from '@/assets/goose.svg'
import jquantsLogo from '@/assets/jquants_logo.svg'
import edinetLogo from '@/assets/edinet_logo.svg'

interface SettingsForm {
    jquantsApiKey: string
    edinetApiKey: string
    mcpEnabled: boolean
}

export function SettingsPage() {
    const [settings, setSettings] = useState<SettingsForm>({
        jquantsApiKey: '',
        edinetApiKey: '',
        mcpEnabled: true,
    })

    const [showKeys, setShowKeys] = useState({
        jquantsApiKey: false,
        edinetApiKey: false,
    })

    const [isSaving, setIsSaving] = useState(false)
    const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle')
    const [errorMessage, setErrorMessage] = useState('')
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
    const [mcpStatus, setMcpStatus] = useState({
        claude: { registered: false, exists: false, path: '' },
        goose: { registered: false, exists: false, path: '' },
        lmstudio: { registered: false, exists: false, path: '' }
    })
    const [isRegistering, setIsRegistering] = useState<string | null>(null)
    const [showSuccessToast, setShowSuccessToast] = useState(false)
    const [lastRegisteredClient, setLastRegisteredClient] = useState('')

    const saveTimerRef = useRef<NodeJS.Timeout | null>(null)
    const isFirstLoad = useRef(true)

    useEffect(() => {
        loadSettings()
        fetchMcpStatus()
    }, [])

    const fetchMcpStatus = async () => {
        if (window.electronAPI?.getMcpStatus) {
            try {
                const status = await window.electronAPI.getMcpStatus()
                setMcpStatus(status)
            } catch (err) {
                console.error('MCPステータスの取得に失敗しました:', err)
            }
        }
    }

    const handleRegisterMcp = async (type: 'claude' | 'goose' | 'lmstudio') => {
        if (!window.electronAPI?.registerMcpClient) return

        setIsRegistering(type)
        try {
            const result = await window.electronAPI.registerMcpClient(type)
            if (result.success) {
                await fetchMcpStatus()
                const displayNames = {
                    claude: 'Claude Desktop',
                    goose: 'Goose Desktop',
                    lmstudio: 'LM Studio'
                }
                setLastRegisteredClient(displayNames[type])
                setShowSuccessToast(true)
                setTimeout(() => setShowSuccessToast(false), 5000)
            }
        } catch (err: any) {
            console.error(`${type}の登録に失敗しました:`, err)
            alert(`${type}の登録に失敗しました。`)
        } finally {
            setIsRegistering(null)
        }
    }


    const loadSettings = async () => {
        try {
            let storedSettings;
            if (window.electronAPI?.getSettings) {
                storedSettings = await window.electronAPI.getSettings()
            } else {
                const stored = localStorage.getItem('mebuki-settings')
                if (stored) storedSettings = JSON.parse(stored)
            }

            if (storedSettings) {
                setSettings({
                    jquantsApiKey: storedSettings.jquantsApiKey || '',
                    edinetApiKey: storedSettings.edinetApiKey || '',
                    mcpEnabled: true,
                })
            }
        } catch (err) {
            console.error('設定の読み込みに失敗しました:', err)
        }
    }

    const triggerAutoSave = useCallback((updatedSettings: SettingsForm) => {
        setHasUnsavedChanges(true)
        if (saveTimerRef.current) clearTimeout(saveTimerRef.current)

        saveTimerRef.current = setTimeout(async () => {
            setIsSaving(true)
            setSaveStatus('idle')
            setErrorMessage('')

            try {
                if (window.electronAPI?.saveSettings) {
                    await window.electronAPI.saveSettings(updatedSettings)
                } else {
                    localStorage.setItem('mebuki-settings', JSON.stringify(updatedSettings))
                }

                await fetch(getApiUrl('/api/settings'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(updatedSettings),
                })

                setSaveStatus('success')
                setHasUnsavedChanges(false)
                setTimeout(() => setSaveStatus('idle'), 2000)
            } catch (err) {
                setSaveStatus('error')
                setErrorMessage(err instanceof Error ? err.message : '保存に失敗しました')
            } finally {
                setIsSaving(false)
            }
        }, 800)
    }, [])

    useEffect(() => {
        if (isFirstLoad.current) {
            isFirstLoad.current = false
            return
        }
        triggerAutoSave(settings)
    }, [settings, triggerAutoSave])

    return (
        <div className="flex-1 flex flex-col min-h-0 bg-background overflow-y-auto relative">
            {/* 背景の装飾的なグラデーション */}
            <div className="absolute top-0 left-1/4 w-96 h-96 bg-primary/5 rounded-full blur-[100px] pointer-events-none" />
            <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-mebuki-brand/5 rounded-full blur-[100px] pointer-events-none" />

            <div className="max-w-4xl mx-auto w-full p-8 space-y-12 pb-24 pt-12 relative z-10">
                {/* ヒーローセクション */}
                <div className="space-y-4 text-center">
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-bold border border-primary/20 animate-in fade-in zoom-in duration-500">
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>Ready to Analyze</span>
                    </div>
                    <h1 className="text-4xl font-black tracking-tight text-foreground sm:text-5xl">
                        AIアシスタントを、<br /><span className="text-mebuki-brand">投資分析のプロ</span>へ。
                    </h1>
                    <p className="text-foreground-muted max-w-lg mx-auto leading-relaxed">
                        APIキーを設定して、AIアシスタント（Claude等）と対話しながら深い銘柄分析を始めましょう。
                    </p>
                </div>

                {/* ステータスバー */}
                <div className="flex flex-col items-center justify-center gap-4 py-2 border-y border-border/40">
                    <div className="flex items-center gap-2 text-xs">
                        {isSaving ? (
                            <span className="text-foreground-muted animate-pulse flex items-center gap-2">
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                保存中...
                            </span>
                        ) : hasUnsavedChanges ? (
                            <span className="text-foreground-muted">入力中...</span>
                        ) : saveStatus === 'success' ? (
                            <span className="text-success flex items-center gap-1">
                                <CheckCircle className="w-3.5 h-3.5" />
                                設定は安全に同期されました
                            </span>
                        ) : saveStatus === 'error' ? (
                            <span className="text-error flex items-center gap-1">
                                <AlertCircle className="w-3.5 h-3.5" />
                                保存エラーが発生しました
                            </span>
                        ) : (
                            <span className="text-foreground-muted opacity-60">変更はリアルタイムでバックエンドに保存されます</span>
                        )}
                    </div>
                    {saveStatus === 'error' && errorMessage && (
                        <p className="text-[10px] text-error font-medium">{errorMessage}</p>
                    )}
                </div>

                {/* ステップコンテナ */}
                <div className="grid grid-cols-1 gap-12">

                    {/* Step 1: API Keys */}
                    <section className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-100">
                        <div className="flex items-center gap-4">
                            <div className="w-10 h-10 rounded-2xl bg-primary text-white flex items-center justify-center font-black shadow-lg shadow-primary/20">1</div>
                            <div>
                                <h2 className="text-xl font-bold text-foreground">APIキーの設定</h2>
                                <p className="text-sm text-foreground-muted">財務データと有報を取得するための鍵を入力します</p>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {/* J-QUANTS */}
                            <div className="group p-6 bg-card border border-border rounded-2xl space-y-4 hover:shadow-xl hover:shadow-primary/5 transition-all duration-300">
                                <div className="flex items-center justify-between">
                                    <div className="h-6">
                                        <img src={jquantsLogo} className="h-full w-auto object-contain brightness-0 dark:invert opacity-80 group-hover:opacity-100 transition-opacity" alt="J-QUANTS" />
                                    </div>
                                    <a
                                        href="https://jpx-jquants.com/ja"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        onClick={(e) => {
                                            if (window.electronAPI?.openExternal) {
                                                e.preventDefault();
                                                window.electronAPI.openExternal('https://jpx-jquants.com/ja');
                                            }
                                        }}
                                        className="text-[10px] text-primary hover:underline flex items-center gap-0.5"
                                    >
                                        発行 <ExternalLink className="w-2.5 h-2.5" />
                                    </a>
                                </div>
                                <div className="relative">
                                    <input
                                        type={showKeys.jquantsApiKey ? 'text' : 'password'}
                                        value={settings.jquantsApiKey}
                                        onChange={(e) => setSettings(prev => ({ ...prev, jquantsApiKey: e.target.value }))}
                                        placeholder="J-QUANTS APIキー"
                                        className="w-full pl-4 pr-14 py-3 rounded-xl border border-border bg-input transition-all focus:ring-2 focus:ring-primary/20 focus:border-primary text-sm font-mono"
                                    />
                                    <button onClick={() => setShowKeys(prev => ({ ...prev, jquantsApiKey: !prev.jquantsApiKey }))} className="absolute right-3 top-1/2 -translate-y-1/2 text-foreground-muted hover:text-foreground">
                                        {showKeys.jquantsApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                    </button>
                                </div>
                            </div>

                            {/* EDINET */}
                            <div className="group p-6 bg-card border border-border rounded-2xl space-y-4 hover:shadow-xl hover:shadow-primary/5 transition-all duration-300">
                                <div className="flex items-center justify-between">
                                    <div className="h-6">
                                        <img src={edinetLogo} className="h-full w-auto object-contain brightness-0 dark:invert opacity-80 group-hover:opacity-100 transition-opacity" alt="EDINET" />
                                    </div>
                                    <a
                                        href="https://api.edinet-fsa.go.jp/api/auth/index.aspx?mode=1"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        onClick={(e) => {
                                            if (window.electronAPI?.openExternal) {
                                                e.preventDefault();
                                                window.electronAPI.openExternal('https://api.edinet-fsa.go.jp/api/auth/index.aspx?mode=1');
                                            }
                                        }}
                                        className="text-[10px] text-primary hover:underline flex items-center gap-0.5"
                                    >
                                        発行 <ExternalLink className="w-2.5 h-2.5" />
                                    </a>
                                </div>
                                <div className="relative">
                                    <input
                                        type={showKeys.edinetApiKey ? 'text' : 'password'}
                                        value={settings.edinetApiKey}
                                        onChange={(e) => setSettings(prev => ({ ...prev, edinetApiKey: e.target.value }))}
                                        placeholder="EDINET APIキー"
                                        className="w-full pl-4 pr-14 py-3 rounded-xl border border-border bg-input transition-all focus:ring-2 focus:ring-primary/20 focus:border-primary text-sm font-mono"
                                    />
                                    <button onClick={() => setShowKeys(prev => ({ ...prev, edinetApiKey: !prev.edinetApiKey }))} className="absolute right-3 top-1/2 -translate-y-1/2 text-foreground-muted hover:text-foreground">
                                        {showKeys.edinetApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                    </button>
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* Step 2: AI Integration */}
                    <section className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-200">
                        <div className="flex items-center gap-4">
                            <div className="w-10 h-10 rounded-2xl bg-primary text-white flex items-center justify-center font-black shadow-lg shadow-primary/20">2</div>
                            <div>
                                <h2 className="text-xl font-bold text-foreground">AIアシスタントとの連携</h2>
                                <p className="text-sm text-foreground-muted">お使いのツールを選んで、mebukiの能力を追加します</p>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
                            {/* Claude Desktop */}
                            <div className="pt-2 pb-6 px-6 bg-card border border-border rounded-2xl space-y-4 hover:shadow-xl transition-all duration-300 relative overflow-hidden group">
                                <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full -mr-16 -mt-16 blur-2xl group-hover:bg-primary/10 transition-colors" />

                                <div className="flex items-center gap-4 relative z-10">
                                    <div className="w-14 h-14 rounded-2xl bg-[#D97757] border border-[#D97757]/10 flex items-center justify-center shadow-md p-2">
                                        <img src={claudeIcon} className="w-full h-full object-contain" alt="Claude" />
                                    </div>
                                    <div>
                                        <h3 className="font-bold text-foreground">Claude Desktop</h3>
                                        <p className="text-[11px] text-foreground-muted">最もおすすめの構成です</p>
                                    </div>
                                    {mcpStatus.claude.registered && (
                                        <div className="ml-auto">
                                            <CheckCircle className="w-5 h-5 text-success" />
                                        </div>
                                    )}
                                </div>

                                <button
                                    disabled={isRegistering !== null || !mcpStatus.claude.exists}
                                    onClick={() => handleRegisterMcp('claude')}
                                    className={cn(
                                        "w-full py-3 rounded-xl text-sm font-bold transition-all flex items-center justify-center gap-2 group/btn relative z-10",
                                        !mcpStatus.claude.exists
                                            ? "bg-foreground-muted/10 text-foreground-muted cursor-not-allowed"
                                            : mcpStatus.claude.registered
                                                ? "bg-success/5 hover:bg-success/10 text-success border border-success/20"
                                                : "bg-mebuki-brand hover:scale-[1.02] active:scale-[0.98] text-white shadow-lg shadow-primary/20"
                                    )}
                                >
                                    {isRegistering === 'claude' ? <Loader2 className="w-4 h-4 animate-spin" /> :
                                        !mcpStatus.claude.exists ? "未インストール" :
                                            mcpStatus.claude.registered ? "連携済み (再設定)" :
                                                <>連携を開始する <ArrowRight className="w-4 h-4 group-hover/btn:translate-x-1 transition-transform" /></>}
                                </button>
                            </div>

                            {/* Goose Desktop */}
                            <div className="pt-2 pb-6 px-6 bg-card border border-border rounded-2xl space-y-4 hover:shadow-xl transition-all duration-300 relative overflow-hidden group">
                                <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full -mr-16 -mt-16 blur-2xl group-hover:bg-primary/10 transition-colors" />

                                <div className="flex items-center gap-4 relative z-10">
                                    <div className="w-14 h-14 rounded-2xl bg-white border border-border flex items-center justify-center shadow-md p-2">
                                        <img src={gooseIcon} className="w-full h-full object-contain" alt="Goose" />
                                    </div>
                                    <div>
                                        <h3 className="font-bold text-foreground">Goose Desktop</h3>
                                        <p className="text-[11px] text-foreground-muted">Block提供のAIアシスタント</p>
                                    </div>
                                    {mcpStatus.goose.registered && (
                                        <div className="ml-auto">
                                            <CheckCircle className="w-5 h-5 text-success" />
                                        </div>
                                    )}
                                </div>

                                <button
                                    disabled={isRegistering !== null || !mcpStatus.goose.exists}
                                    onClick={() => handleRegisterMcp('goose')}
                                    className={cn(
                                        "w-full py-3 rounded-xl text-sm font-bold transition-all flex items-center justify-center gap-2 group/btn relative z-10",
                                        !mcpStatus.goose.exists
                                            ? "bg-foreground-muted/10 text-foreground-muted cursor-not-allowed"
                                            : mcpStatus.goose.registered
                                                ? "bg-success/5 hover:bg-success/10 text-success border border-success/20"
                                                : "bg-mebuki-brand hover:scale-[1.02] active:scale-[0.98] text-white shadow-lg shadow-primary/20"
                                    )}
                                >
                                    {isRegistering === 'goose' ? <Loader2 className="w-4 h-4 animate-spin" /> :
                                        !mcpStatus.goose.exists ? "未インストール" :
                                            mcpStatus.goose.registered ? "連携済み (再設定)" :
                                                <>連携を開始する <ArrowRight className="w-4 h-4 group-hover/btn:translate-x-1 transition-transform" /></>}
                                </button>
                            </div>
                        </div>

                        {/* Tips */}
                        <div className="p-6 rounded-2xl bg-foreground-muted/5 border border-border/60 flex gap-4">
                            <div className="w-10 h-10 rounded-xl bg-background flex items-center justify-center text-primary flex-shrink-0">
                                <MessageSquare className="w-5 h-5" />
                            </div>
                            <div className="space-y-1">
                                <h4 className="text-sm font-bold text-foreground">何ができるようになりますか？</h4>
                                <p className="text-xs text-foreground-muted leading-relaxed">
                                    「トヨタの直近3年間のキャッシュフローを分析して」「この企業の事業リスクを有報から要約して」など、AIアシスタントに聞くだけでmebukiが裏側でデータを精査し、その回答をグラフ付きで得られるようになります。
                                </p>
                            </div>
                        </div>
                    </section>

                </div>
            </div>

            {/* Success Notification */}
            {showSuccessToast && (
                <div className="fixed bottom-8 right-8 bg-card border border-success/20 shadow-2xl rounded-2xl p-6 flex items-start gap-5 animate-in fade-in slide-in-from-right-8 duration-500 z-50 max-w-sm border-l-4 border-l-success">
                    <div className="w-12 h-12 rounded-2xl bg-success/10 flex items-center justify-center text-success flex-shrink-0">
                        <CheckCircle className="w-8 h-8" />
                    </div>
                    <div className="space-y-2">
                        <h4 className="text-sm font-black text-foreground leading-none">連携完了！</h4>
                        <p className="text-xs text-foreground-muted leading-relaxed">
                            設定を反映させるため、<span className="font-bold text-foreground">{lastRegisteredClient} を一度終了して再起動</span>してください。
                        </p>
                        <button
                            onClick={() => setShowSuccessToast(false)}
                            className="text-[10px] font-bold text-success hover:underline"
                        >
                            閉じる
                        </button>
                    </div>
                </div>
            )}
        </div>
    )
}
