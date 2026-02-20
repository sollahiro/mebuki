/**
 * 型定義
 */

// 年度別財務データ
export interface YearData {
  // --- 旧来のフラットな構造 (互換性維持のため保持) ---
  fy_end: string
  sales: number | null
  op: number | null
  np: number | null
  eq: number | null
  cfo: number | null
  cfi: number | null
  fcf: number | null
  roe: number | null
  eps: number | null
  bps: number | null
  adjusted_eps?: number | null
  adjusted_bps?: number | null
  adjustment_ratio?: number | null
  price: number | null
  per: number | null
  pbr: number | null
  dividend_yield?: number | null
  payout_ratio?: number | null
  simple_roic?: number | null
  cf_conversion_rate?: number | null
  cash_eq?: number | null
  financial_period?: string

  // --- 新規：グループ化された構造 ---
  RawData: {
    CurPerType: string
    CurFYSt: string
    CurFYEn: string
    DiscDate: string
    Sales: number | null
    OP: number | null
    NP: number | null
    Eq: number | null
    CFO: number | null
    CFI: number | null
    EPS: number | null
    BPS: number | null
    AvgSh: number | null
    DivTotalAnn: number | null
    PayoutRatioAnn: number | null
    CashEq: number | null
    DivAnn: number | null
    NxFDivAnn: number | null
  }
  CalculatedData: {
    Sales: number | null
    OP: number | null
    NP: number | null
    Eq: number | null
    CFO: number | null
    CFI: number | null
    CFC: number | null
    PayoutRatio: number | null
    AdjustmentRatio: number | null
    AdjustedEPS: number | null
    AdjustedBPS: number | null
    CFCVR: number | null
    ROE: number | null
    SimpleROIC: number | null
    Price: number | null
    PER: number | null
    PBR: number | null
    CashEq: number | null
    FinancialPeriod: string
  }
}

// 指標データ
export interface Metrics {
  years: YearData[]
  analysis_years: number
}

// EDINETデータ
export interface EdinetData {
  docID: string
  submitDate: string
  pdf_path?: string
  edinetCode?: string
  docType: string
  docTypeCode?: string
  docDescription?: string
  filerName?: string
  fiscal_year?: number
  jquants_fy_end?: string
}

// 分析結果
export interface AnalysisResult {
  code: string
  name: string
  name_en?: string
  sector_33?: string
  sector_33_name?: string
  sector_17?: string
  sector_17_name?: string
  market?: string
  market_name?: string
  metrics: Metrics
  edinet_data?: Record<string, EdinetData[]>
  analyzed_at: string
  status?: string  // 実行状態 (initializing, fetching_metrics, analyzing_llm, etc.)
  message?: string // 状態メッセージ
  summary?: string  // 企業概要（50文字以内）
}

// 履歴アイテム
export interface HistoryItem {
  code: string
  name: string
  timestamp: string
}

// 進捗状態
export interface ProgressState {
  step: string
  progress: number
  message: string
  company_code?: string  // 銘柄コード(例: 72030)
  company_name?: string  // 銘柄名(例: トヨタ自動車)
  data?: any             // 中間取得データ
}

// 設定
export interface Settings {
  jquantsApiKey: string
  edinetApiKey: string
  geminiApiKey: string
  llmProvider: 'gemini' | 'ollama'
}


// グラフデータ
export interface ChartDataPoint {
  year: string
  [key: string]: string | number | null
}

declare global {
  interface Window {
    electronAPI: {
      getSettings: () => Promise<any>
      saveSettings: (settings: any) => Promise<any>
      getAppInfo: () => Promise<{ projectRoot: string }>
      getMcpStatus: () => Promise<any>
      registerMcpClient: (type: 'claude' | 'goose' | 'lmstudio') => Promise<{ success: boolean }>
      openExternal: (url: string) => Promise<{ success: boolean; error?: string }>
    }
  }
}
