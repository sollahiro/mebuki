/**
 * 型定義
 */

// 年度別財務データ
export interface YearData {
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
  adjusted_eps?: number | null  // 調整後EPS（株式分割調整済み）
  adjusted_bps?: number | null  // 調整後BPS（株式分割調整済み）
  adjustment_ratio?: number | null  // 調整倍率
  price: number | null
  per: number | null
  pbr: number | null
  dividend_yield?: number | null
  payout_ratio?: number | null
  simple_roic?: number | null
  cf_conversion_rate?: number | null
  cash_eq?: number | null  // 現金及び現金同等物
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
  management_policy: string
  docType: string
  docTypeCode?: string
  docDescription?: string
  filerName?: string
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
  edinet_data?: Record<number, EdinetData>
  llm_financial_analysis?: FinancialAnalysisResult | null
  analyzed_at: string
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

// 財務分析結果
export interface FinancialAnalysisSection {
  section_id: number
  title: string
  analysis: string
}

export interface FinancialAnalysisResult {
  error?: string
  sections?: FinancialAnalysisSection[]
  text?: string  // フォールバック用
}

// グラフデータ
export interface ChartDataPoint {
  year: string
  [key: string]: string | number | null
}
