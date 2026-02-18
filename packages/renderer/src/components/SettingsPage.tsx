import { useState, useEffect, useCallback, useRef } from 'react'
import { Key, Eye, EyeOff, AlertCircle, CheckCircle, Copy, ExternalLink, Cpu, ChevronDown, ChevronUp, Loader2, Settings, MessageSquare } from 'lucide-react'
import { cn } from '../lib/utils'
import { getApiUrl } from '../lib/api'
import claudeIcon from '@/assets/claude-color.svg'
import gooseIcon from '@/assets/goose.svg'
import mebukiMcpIcon from '@/assets/mcp_icon.svg'
// import lmstudioIcon from '@/assets/lmstudio-white.svg'

interface SettingsPageProps {
}

interface SettingsForm {
    jquantsApiKey: string
    edinetApiKey: string
    mcpEnabled: boolean
}

export function SettingsPage({ }: SettingsPageProps) {
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
    const [projectRoot, setProjectRoot] = useState('')
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
    const [mcpStatus, setMcpStatus] = useState({
        claude: { registered: false, exists: false, path: '' },
        goose: { registered: false, exists: false, path: '' },
        lmstudio: { registered: false, exists: false, path: '' }
    })
    const [isRegistering, setIsRegistering] = useState<string | null>(null)
    const [showAdvancedMcp, setShowAdvancedMcp] = useState(false)
    const [showSuccessToast, setShowSuccessToast] = useState(false)
    const [lastRegisteredClient, setLastRegisteredClient] = useState('')

    const saveTimerRef = useRef<NodeJS.Timeout | null>(null)
    const isFirstLoad = useRef(true)

    // Load settings on mount
    useEffect(() => {
        loadSettings()
        fetchAppInfo()
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
            const detail = err?.message || JSON.stringify(err)
            alert(`${type}の登録に失敗しました。\n\nエラー内容: ${detail}\n\n詳細は開発者コンソールを確認してください。`)
        } finally {
            setIsRegistering(null)
        }
    }

    const fetchAppInfo = async () => {
        if (window.electronAPI?.getAppInfo) {
            try {
                const info = await window.electronAPI.getAppInfo()
                if (info && info.projectRoot) {
                    setProjectRoot(info.projectRoot)
                }
            } catch (err) {
                console.error('AppInfoの取得に失敗しました:', err)
            }
        }
    }


    const loadSettings = async () => {
        try {
            let storedSettings;
            if (window.electronAPI?.getSettings) {
                storedSettings = await window.electronAPI.getSettings()
            } else {
                const stored = localStorage.getItem('mebuki-settings')
                if (stored) {
                    storedSettings = JSON.parse(stored)
                }
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
        }, 800) // 800ms debounce
    }, [])

    // 自動保存のトリガー（設定が変更されたとき）
    useEffect(() => {
        if (isFirstLoad.current) {
            isFirstLoad.current = false
            return
        }
        triggerAutoSave(settings)
    }, [settings, triggerAutoSave])


    const toggleShowKey = (key: keyof typeof showKeys) => {
        setShowKeys((prev) => ({ ...prev, [key]: !prev[key] }))
    }

    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text)
    }

    return (
        <div className="flex-1 flex flex-col min-h-0 bg-background overflow-y-auto">
            <div className="max-w-6xl mx-auto w-full p-8 space-y-8 pb-12 pt-12">
                <div className="flex items-center justify-between">
                    <h1 className="text-2xl font-bold text-foreground">設定</h1>
                    <div className="flex items-center gap-2 text-sm">
                        {isSaving ? (
                            <span className="text-foreground-muted animate-pulse">保存中...</span>
                        ) : hasUnsavedChanges ? (
                            <span className="text-foreground-muted">入力中...</span>
                        ) : saveStatus === 'success' ? (
                            <span className="text-success flex items-center gap-1">
                                <CheckCircle className="w-4 h-4" />
                                保存済み
                            </span>
                        ) : saveStatus === 'error' ? (
                            <span className="text-error flex items-center gap-1">
                                <AlertCircle className="w-4 h-4" />
                                保存エラー
                            </span>
                        ) : (
                            <span className="text-foreground-muted opacity-50">設定は自動的に保存されます</span>
                        )}
                    </div>
                </div>

                {saveStatus === 'error' && (
                    <div className="flex items-center gap-2 p-4 bg-error/10 border border-error/20 rounded-lg text-error animate-in fade-in slide-in-from-top-2 duration-300">
                        <AlertCircle className="w-5 h-5" />
                        <span className="font-medium text-sm">{errorMessage}</span>
                    </div>
                )}

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
                    {/* Left Column: API & AI Settings */}
                    <div className="space-y-12">
                        {/* API Keys Section */}
                        <section className="space-y-6">
                            <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground-muted">API キー設定</h2>

                            {/* J-QUANTS API Key */}
                            <div className="space-y-2">
                                <label className="text-sm font-medium text-foreground flex items-center gap-2">
                                    <Key className="w-4 h-4 text-primary" />
                                    J-QUANTS APIキー
                                    <span className="text-error font-bold">*</span>
                                </label>
                                <div className="relative">
                                    <input
                                        type={showKeys.jquantsApiKey ? 'text' : 'password'}
                                        value={settings.jquantsApiKey}
                                        onChange={(e) =>
                                            setSettings((prev) => ({ ...prev, jquantsApiKey: e.target.value }))
                                        }
                                        placeholder="APIキーを入力"
                                        className={cn(
                                            'w-full px-4 py-2.5 pr-10 rounded-md border border-border bg-input transition-all duration-200',
                                            'text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary'
                                        )}
                                    />
                                    <button
                                        type="button"
                                        onClick={() => toggleShowKey('jquantsApiKey')}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-foreground-muted hover:text-foreground transition-colors"
                                    >
                                        {showKeys.jquantsApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                    </button>
                                </div>
                                <div className="flex items-center justify-between">
                                    <p className="text-xs text-foreground-muted">財務データ取得に必要です（必須）</p>
                                    <a
                                        href="https://jpx-jquants.com/ja"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-xs text-primary hover:underline flex items-center gap-1"
                                    >
                                        登録・発行サイトへ
                                        <ExternalLink className="w-3 h-3" />
                                    </a>
                                </div>
                            </div>

                            {/* EDINET API Key */}
                            <div className="space-y-2">
                                <label className="text-sm font-medium text-foreground flex items-center gap-2">
                                    <Key className="w-4 h-4 text-primary" />
                                    EDINET APIキー
                                    <span className="text-error font-bold">*</span>
                                </label>
                                <div className="relative">
                                    <input
                                        type={showKeys.edinetApiKey ? 'text' : 'password'}
                                        value={settings.edinetApiKey}
                                        onChange={(e) =>
                                            setSettings((prev) => ({ ...prev, edinetApiKey: e.target.value }))
                                        }
                                        placeholder="APIキーを入力"
                                        className={cn(
                                            'w-full px-4 py-2.5 pr-10 rounded-md border border-border bg-input transition-all duration-200',
                                            'text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary'
                                        )}
                                    />
                                    <button
                                        type="button"
                                        onClick={() => toggleShowKey('edinetApiKey')}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-foreground-muted hover:text-foreground transition-colors"
                                    >
                                        {showKeys.edinetApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                    </button>
                                </div>
                                <div className="flex items-center justify-between">
                                    <p className="text-xs text-foreground-muted">有価証券報告書の取得に必要です（必須）</p>
                                    <a
                                        href="https://api.edinet-fsa.go.jp/api/auth/index.aspx?mode=1"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-xs text-primary hover:underline flex items-center gap-1"
                                    >
                                        登録・発行サイトへ
                                        <ExternalLink className="w-3 h-3" />
                                    </a>
                                </div>
                            </div>
                        </section>


                    </div>

                    {/* Right Column: MCP Settings */}
                    <div className="space-y-12">
                        <section className="space-y-6">
                            <div className="flex items-center justify-between">
                                <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground-muted flex items-center gap-2">
                                    <Cpu className="w-4 h-4" />
                                    AI アシスタント連携
                                </h2>
                            </div>

                            <div className="p-4 bg-foreground-muted/5 border border-border rounded-lg space-y-4">
                                <p className="text-sm text-foreground font-medium">
                                    AIアシスタントと話しながら、気になる銘柄を深掘りしましょう。
                                </p>
                                <div className="space-y-3 pt-2 border-t border-border/50">
                                    <ul className="text-sm text-foreground-muted space-y-3">
                                        <li className="flex items-start gap-2.5">
                                            <MessageSquare className="w-3.5 h-3.5 text-primary/70 mt-0.5 flex-shrink-0" />
                                            <span>「トヨタ の直近3年間の業績推移をまとめて」</span>
                                        </li>
                                        <li className="flex items-start gap-2.5">
                                            <MessageSquare className="w-3.5 h-3.5 text-primary/70 mt-0.5 flex-shrink-0" />
                                            <span>「最新の有価証券報告書から、事業リスクについて要約して」</span>
                                        </li>
                                        <li className="flex items-start gap-2.5">
                                            <MessageSquare className="w-3.5 h-3.5 text-primary/70 mt-0.5 flex-shrink-0" />
                                            <span>「この企業の資本効率（ROE）の推移はどうなっている？」</span>
                                        </li>
                                    </ul>
                                </div>
                            </div>

                            {/* Client Cards */}
                            <div className="grid grid-cols-1 gap-4">
                                {/* Claude Desktop Card */}
                                <div className="p-5 bg-card border border-border rounded-xl space-y-4 shadow-sm hover:shadow-md transition-shadow">
                                    <div className="flex items-start justify-between">
                                        <div className="flex items-center gap-4">
                                            <div className="w-12 h-12 rounded-[10px] bg-white border border-border flex items-center justify-center shadow-sm">
                                                <img src={claudeIcon} className="w-7 h-7" alt="Claude" />
                                            </div>
                                            <div>
                                                <h3 className="font-bold text-foreground">Claude Desktop</h3>
                                                <p className="text-xs text-foreground-muted">Anthropic提供のAIアシスタント</p>
                                            </div>
                                        </div>
                                        {mcpStatus.claude.registered && (
                                            <span className="flex items-center gap-1 text-[10px] font-bold text-success bg-success/10 px-2 py-0.5 rounded-full border border-success/20">
                                                <CheckCircle className="w-3 h-3" />
                                                連携済み
                                            </span>
                                        )}
                                    </div>
                                    <button
                                        disabled={isRegistering !== null || !mcpStatus.claude.exists}
                                        onClick={() => handleRegisterMcp('claude')}
                                        className={cn(
                                            "w-full py-2.5 rounded-lg text-sm font-semibold transition-all flex items-center justify-center gap-2",
                                            !mcpStatus.claude.exists
                                                ? "bg-[#4b5563] text-white cursor-not-allowed border-transparent shadow-sm"
                                                : mcpStatus.claude.registered
                                                    ? "bg-foreground-muted/5 hover:bg-foreground-muted/10 text-foreground border border-border"
                                                    : "bg-[#35C85F] bg-gradient-to-br from-[#35C85F] to-[#1BBED0] hover:opacity-90 text-white shadow-lg shadow-primary/20"
                                        )}
                                    >
                                        {isRegistering === 'claude' ? (
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                        ) : !mcpStatus.claude.exists ? (
                                            <>インストールされていません</>
                                        ) : mcpStatus.claude.registered ? (
                                            <>設定を更新 (再同期)</>
                                        ) : (
                                            <>Claude Desktop と連携</>
                                        )}
                                    </button>
                                </div>

                                <div className="p-5 bg-card border border-border rounded-xl space-y-4 shadow-sm hover:shadow-md transition-shadow">
                                    <div className="flex items-start justify-between">
                                        <div className="flex items-center gap-4">
                                            <div className="w-12 h-12 rounded-[10px] bg-white border border-border flex items-center justify-center shadow-sm">
                                                <img src={gooseIcon} className="w-7 h-7" alt="Goose Desktop" />
                                            </div>
                                            <div>
                                                <h3 className="font-bold text-foreground">Goose Desktop</h3>
                                                <p className="text-xs text-foreground-muted">Block提供のAIエージェント</p>
                                            </div>
                                        </div>
                                        {mcpStatus.goose.registered && (
                                            <span className="flex items-center gap-1 text-[10px] font-bold text-success bg-success/10 px-2 py-0.5 rounded-full border border-success/20">
                                                <CheckCircle className="w-3 h-3" />
                                                連携済み
                                            </span>
                                        )}
                                    </div>
                                    <button
                                        disabled={isRegistering !== null || !mcpStatus.goose.exists}
                                        onClick={() => handleRegisterMcp('goose')}
                                        className={cn(
                                            "w-full py-2.5 rounded-lg text-sm font-semibold transition-all flex items-center justify-center gap-2",
                                            !mcpStatus.goose.exists
                                                ? "bg-[#4b5563] text-white cursor-not-allowed border-transparent shadow-sm"
                                                : mcpStatus.goose.registered
                                                    ? "bg-foreground-muted/5 hover:bg-foreground-muted/10 text-foreground border border-border"
                                                    : "bg-[#35C85F] bg-gradient-to-br from-[#35C85F] to-[#1BBED0] hover:opacity-90 text-white shadow-lg shadow-primary/20"
                                        )}
                                    >
                                        {isRegistering === 'goose' ? (
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                        ) : !mcpStatus.goose.exists ? (
                                            <>インストールされていません</>
                                        ) : mcpStatus.goose.registered ? (
                                            <>設定を更新 (再同期)</>
                                        ) : (
                                            <>Goose Desktop と連携</>
                                        )}
                                    </button>
                                </div>

                                {/* LM Studio 連携 - 一時非表示 */}
                                {/* 
                                 <div className="p-5 bg-card border border-border rounded-xl space-y-4 shadow-sm hover:shadow-md transition-shadow">
                                     <div className="flex items-start justify-between">
                                         <div className="flex items-center gap-4">
                                             <div
                                                 className="w-12 h-12 rounded-[10px] border border-border flex items-center justify-center shadow-sm overflow-hidden"
                                                 style={{ background: 'radial-gradient(circle at top left, #6760CF, #4338CA)' }}
                                             >
                                                 <img src={lmstudioIcon} className="w-8 h-8" alt="LM Studio" />
                                             </div>
                                             <div>
                                                 <h3 className="font-bold text-foreground">LM Studio</h3>
                                                 <p className="text-xs text-foreground-muted">Element Labs提供のローカルLLMツール</p>
                                             </div>
                                         </div>
                                         {mcpStatus.lmstudio.registered && (
                                             <span className="flex items-center gap-1 text-[10px] font-bold text-success bg-success/10 px-2 py-0.5 rounded-full border border-success/20">
                                                 <CheckCircle className="w-3 h-3" />
                                                 連携済み
                                             </span>
                                         )}
                                     </div>
                                     <button
                                         disabled={isRegistering !== null || !mcpStatus.lmstudio.exists}
                                         onClick={() => handleRegisterMcp('lmstudio')}
                                         className={cn(
                                             "w-full py-2.5 rounded-lg text-sm font-semibold transition-all flex items-center justify-center gap-2",
                                             !mcpStatus.lmstudio.exists
                                                 ? "bg-[#4b5563] text-white cursor-not-allowed border-transparent shadow-sm"
                                                 : mcpStatus.lmstudio.registered
                                                     ? "bg-foreground-muted/5 hover:bg-foreground-muted/10 text-foreground border border-border"
                                                     : "bg-[#35C85F] bg-gradient-to-br from-[#35C85F] to-[#1BBED0] hover:opacity-90 text-white shadow-lg shadow-primary/20"
                                         )}
                                     >
                                         {isRegistering === 'lmstudio' ? (
                                             <Loader2 className="w-4 h-4 animate-spin" />
                                         ) : !mcpStatus.lmstudio.exists ? (
                                             <>インストールされていません</>
                                         ) : mcpStatus.lmstudio.registered ? (
                                             <>設定を更新 (再同期)</>
                                         ) : (
                                             <>LM Studio と連携</>
                                         )}
                                     </button>
                                 </div>
                                 */}
                            </div>

                            {/* Advanced Section */}
                            <div className="pt-4">
                                <button
                                    onClick={() => setShowAdvancedMcp(!showAdvancedMcp)}
                                    className="flex items-center gap-2 text-xs text-foreground-muted hover:text-foreground transition-colors group"
                                >
                                    <Settings className="w-3.5 h-3.5 group-hover:rotate-45 transition-transform duration-300" />
                                    <span>高度な設定・手動連携</span>
                                    {showAdvancedMcp ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                                </button>

                                {showAdvancedMcp && (
                                    <div className="mt-4 p-6 bg-foreground-muted/5 border border-dashed border-border rounded-xl space-y-6 animate-in fade-in slide-in-from-top-2 duration-300">
                                        {/* mebuki MCP Server Icon & Identity */}
                                        <div className="flex items-center gap-4 pb-4 border-b border-border/50">
                                            <div className="w-16 h-16 rounded-xl bg-white border border-border flex items-center justify-center shadow-md overflow-hidden p-2">
                                                <img src={mebukiMcpIcon} className="w-full h-full object-contain" alt="mebuki MCP" />
                                            </div>
                                            <div>
                                                <h4 className="font-bold text-foreground">mebuki MCP Server</h4>
                                                <p className="text-[11px] text-foreground-muted">Built-in Expert Analysis Tool</p>
                                            </div>
                                        </div>

                                        <div className="space-y-4">
                                            <div className="flex items-center justify-between">
                                                <label className="text-sm font-medium text-foreground flex items-center gap-2">
                                                    <ExternalLink className="w-4 h-4 text-primary" />
                                                    構成設定 (JSON)
                                                </label>
                                                <button
                                                    onClick={() => {
                                                        copyToClipboard(JSON.stringify({
                                                            "mcpServers": {
                                                                "mebuki": {
                                                                    "command": "node",
                                                                    "args": [`${projectRoot || '/Users/shutosorahiro/mebuki'}/packages/mcp/dist/index.js`],
                                                                    "env": { "MEBUKI_BACKEND_URL": "http://localhost:8765" }
                                                                }
                                                            }
                                                        }, null, 2))
                                                    }}
                                                    className="text-xs text-primary hover:text-primary-hover flex items-center gap-1 transition-colors"
                                                >
                                                    <Copy className="w-3 h-3" />
                                                    コピー
                                                </button>
                                            </div>
                                            <div className="relative group">
                                                <pre className="p-4 bg-input border border-border rounded-lg text-[11px] font-mono overflow-x-auto text-foreground-muted">
                                                    {JSON.stringify({
                                                        "mcpServers": {
                                                            "mebuki": {
                                                                "command": "node",
                                                                "args": [`${projectRoot || '/Users/shutosorahiro/mebuki'}/packages/mcp/dist/index.js`],
                                                                "env": { "MEBUKI_BACKEND_URL": "http://localhost:8765" },
                                                                "metadata": {
                                                                    "icon": `${projectRoot || '/Users/shutosorahiro/mebuki'}/packages/mcp/icon.png`,
                                                                    "description": "Expert investment analyst tool for Japanese stocks."
                                                                }
                                                            }
                                                        }
                                                    }, null, 2)}
                                                </pre>
                                            </div>
                                        </div>

                                        <div className="space-y-3">
                                            <h4 className="text-xs font-semibold text-foreground">手動設定の手順:</h4>
                                            <ol className="text-[11px] text-foreground-muted list-decimal list-inside space-y-2 leading-relaxed">
                                                <li>構成設定をコピーします。</li>
                                                <li>利用したいクライアント（Cursor等）の MCP 設定を開きます。</li>
                                                <li><code>"mcpServers"</code> 内に貼り付けます。</li>
                                                <li>クライアントを再起動してツールが認識されるか確認してください。</li>
                                            </ol>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </section>
                    </div>
                </div>
            </div>

            {/* Success Toast */}
            {showSuccessToast && (
                <div className="fixed bottom-6 right-6 bg-card border border-success/30 shadow-2xl rounded-lg p-4 flex items-center gap-4 animate-in fade-in slide-in-from-right-8 duration-300 z-50 max-w-sm">
                    <div className="w-10 h-10 rounded-full bg-success/10 flex items-center justify-center text-success flex-shrink-0">
                        <CheckCircle className="w-6 h-6" />
                    </div>
                    <div className="space-y-1">
                        <h4 className="text-sm font-bold text-foreground">連携設定を完了しました</h4>
                        <p className="text-xs text-foreground-muted leading-relaxed">
                            設定を反映させるため、<b>{lastRegisteredClient} を再起動</b>してください。
                        </p>
                    </div>
                    <button
                        onClick={() => setShowSuccessToast(false)}
                        className="p-1 hover:bg-foreground-muted/10 rounded-full text-foreground-muted transition-colors"
                    >
                        <EyeOff className="w-4 h-4" />
                    </button>
                </div>
            )}
        </div>
    )
}
