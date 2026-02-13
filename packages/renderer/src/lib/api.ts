/**
 * API クライアント
 */

/**
 * Electron環境（file://）とWeb環境の両方に対応したAPIのベースURLを取得
 */
export const getApiUrl = (path: string): string =>
  window.location.protocol === 'file:' ? `http://127.0.0.1:8765${path}` : path;

export interface ApiError {
  message: string
  status?: number
}

/**
 * APIリクエストを実行
 */
async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = getApiUrl(endpoint)

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `HTTP Error: ${response.status}`)
  }

  return response.json()
}

/**
 * ヘルスチェック
 */
export async function healthCheck(): Promise<{ status: string; message: string }> {
  return request('/api/health')
}

/**
 * 設定を更新
 */
export async function updateSettings(settings: {
  jquantsApiKey?: string
  edinetApiKey?: string
}): Promise<{ status: string; message: string }> {
  return request('/api/settings', {
    method: 'POST',
    body: JSON.stringify(settings),
  })
}

/**
 * 設定を取得
 */
export async function getSettings(): Promise<{
  jquantsApiKey?: string
  edinetApiKey?: string
}> {
  return request('/api/settings')
}

/**
 * 分析を実行（非ストリーミング）
 */
export async function analyzeStock(
  code: string,
  forceRefresh = false
): Promise<{ status: string; data: unknown }> {
  return request(`/api/analyze/${code}?force_refresh=${forceRefresh}`, {
    method: 'POST',
  })
}

/**
 * 分析履歴を取得
 */
export async function getHistory(): Promise<{
  status: string
  data: { code: string; name: string; timestamp: string }[]
}> {
  return request('/api/history')
}

/**
 * キャッシュを削除
 */
export async function clearCache(code: string): Promise<{ status: string; message: string }> {
  return request(`/api/cache/${code}`, {
    method: 'DELETE',
  })
}
/**
 * 銘柄検索（サジェスト用）
 */
export async function searchCompanies(query: string): Promise<{
  code: string
  name: string
  sector: string
  market: string
}[]> {
  return request(`/api/companies/search?query=${encodeURIComponent(query)}`)
}
