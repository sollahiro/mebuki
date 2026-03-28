import asyncio
import logging
import json
import ssl
import zipfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

import aiohttp
import certifi

from ..constants.api import EDINET_API_BASE_URL
from ..utils.fiscal_year import normalize_date_format, parse_date_string

logger = logging.getLogger(__name__)

class EdinetAPIClient:
    """EDINET API v2 クライアント"""

    def __init__(self, api_key: Optional[str] = None, cache_dir: Optional[str] = None):
        self.api_key = api_key
        self.base_url = EDINET_API_BASE_URL
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path("tmp_cache") / "edinet"

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_loop: Optional[asyncio.AbstractEventLoop] = None

    def update_api_key(self, api_key: str) -> None:
        """APIキーを更新します。"""
        self.api_key = api_key.strip() if api_key else ""
        self._session = None
        self._session_loop = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """セッションを遅延作成して返す"""
        current_loop = asyncio.get_running_loop()
        if self._session is not None and not self._session.closed and self._session_loop is not current_loop:
            await self._session.close()
            self._session = None
        if self._session is None or self._session.closed:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self._session = aiohttp.ClientSession(connector=connector)
            self._session_loop = current_loop
        return self._session

    async def close(self) -> None:
        """セッションを明示的にクローズする"""
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None
        self._session_loop = None

    async def _request(self, endpoint: str, params: Dict[str, Any] = None, max_retries: int = 3) -> Dict[str, Any]:
        """リトライ機能付きAPIリクエスト実行（JSON応答）"""
        if not self.api_key:
            raise ValueError("EDINET_API_KEY is not set")

        url = f"{self.base_url}{endpoint}"
        params = dict(params or {})
        params["Subscription-Key"] = self.api_key

        last_exception = None
        session = await self._get_session()
        timeout = aiohttp.ClientTimeout(total=30)

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = 2 ** attempt
                    logger.warning(f"⚠️ [EDINET API] Retry attempt {attempt+1}/{max_retries} after {wait_time}s...")
                    await asyncio.sleep(wait_time)

                async with session.get(url, params=params, timeout=timeout) as response:
                    # JSONボディのビジネスエラーをステータスコードより先にチェック
                    try:
                        data = await response.json(content_type=None)
                        status_code_in_body = data.get("statusCode")
                        if status_code_in_body and status_code_in_body != 200:
                            message = data.get("message", "Unknown error")
                            logger.error(f"❌ [EDINET API] Business logic error: {status_code_in_body} - {message}")
                            if status_code_in_body == 401:
                                raise ValueError(f"EDINET APIキーが無効です: {message}")
                            raise aiohttp.ClientResponseError(
                                response.request_info,
                                response.history,
                                status=status_code_in_body,
                                message=f"EDINET API error: {status_code_in_body} - {message}",
                            )
                        response.raise_for_status()
                        return data
                    except ValueError as e:
                        if "EDINET APIキーが無効です" in str(e):
                            raise
                        # JSON以外のレスポンス
                        response.raise_for_status()
                        return {}

            except (aiohttp.ClientResponseError, aiohttp.ClientError, ValueError) as e:
                last_exception = e
                if isinstance(e, ValueError) and "EDINET APIキーが無効です" in str(e):
                    raise

                status_code = getattr(e, "status", None)
                if status_code in [429, 500, 502, 503, 504] or isinstance(e, aiohttp.ClientConnectorError):
                    continue
                else:
                    logger.error(f"❌ [EDINET API] Non-retryable error: {e}")
                    raise

        logger.error(f"❌ [EDINET API] All {max_retries} attempts failed. Last error: {last_exception}")
        raise last_exception

    async def _request_binary(self, endpoint: str, params: Dict[str, Any] = None, max_retries: int = 3) -> bytes:
        """リトライ機能付きAPIリクエスト実行（バイナリ応答）"""
        if not self.api_key:
            raise ValueError("EDINET_API_KEY is not set")

        url = f"{self.base_url}{endpoint}"
        params = dict(params or {})
        params["Subscription-Key"] = self.api_key

        last_exception = None
        session = await self._get_session()
        timeout = aiohttp.ClientTimeout(total=120)

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = 2 ** attempt
                    logger.warning(f"⚠️ [EDINET API] Retry attempt {attempt+1}/{max_retries} after {wait_time}s...")
                    await asyncio.sleep(wait_time)

                async with session.get(url, params=params, timeout=timeout) as response:
                    response.raise_for_status()
                    return await response.read()

            except (aiohttp.ClientResponseError, aiohttp.ClientError) as e:
                last_exception = e
                status_code = getattr(e, "status", None)
                if status_code in [429, 500, 502, 503, 504] or isinstance(e, aiohttp.ClientConnectorError):
                    continue
                raise

        raise last_exception

    def _get_search_cache_key(self, date_str: str) -> str:
        """検索用キャッシュキー生成（日付ベース）"""
        return f"search_{date_str}.json"

    def _load_search_cache(self, filename: str) -> Optional[List[Dict[str, Any]]]:
        """キャッシュから検索結果をロード"""
        cache_path = self.cache_dir / filename
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Cache load failed: {e}")
        return None

    def _save_search_cache(self, filename: str, data: List[Dict[str, Any]]) -> None:
        """検索結果をキャッシュに保存"""
        cache_path = self.cache_dir / filename
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")

    async def search_documents(
        self,
        code: str,
        years: Optional[List[int]] = None,
        doc_type_code: Optional[str] = None,
        jquants_data: Optional[List[Dict[str, Any]]] = None,
        edinet_code: Optional[str] = None,
        max_documents: int = 2
    ) -> List[Dict[str, Any]]:
        """
        J-QUANTSのレコードに基づいてEDINET書類を検索（期間ベース）

        最適化：提出期限（会計期間終了から90日/45日）から決算発表日までを「後方探索」し、
        かつ日付ごとのリスト取得を「並列化」することで高速化します。
        """
        if not self.api_key or not jquants_data:
            return []

        all_documents = []
        now = datetime.now()
        code_4digit = code[:4] if len(code) >= 4 else code

        # 最大並列数（EDINET APIの負荷に配慮して10程度）
        MAX_WORKERS = 10

        # 各レコードを直接処理
        for record in jquants_data:
            if len(all_documents) >= max_documents:
                logger.info(f"✅ [EDINET] Found {max_documents} documents, stopping search early.")
                break

            fy_end = record.get("CurFYEn", "")
            per_en = record.get("CurPerEn", "")
            fy_st = record.get("CurFYSt", "")
            disc_date_str = record.get("DiscDate", "")
            period_type = record.get("CurPerType") or record.get("period_type", "FY")

            fiscal_year = record.get("fiscal_year")
            if not fiscal_year and fy_st:
                fy_st_date = parse_date_string(fy_st)
                if fy_st_date:
                    fiscal_year = fy_st_date.year

            target_period_end_str = per_en if period_type != "FY" and per_en else fy_end
            period_end_date = parse_date_string(target_period_end_str)
            disc_date_formatted = normalize_date_format(disc_date_str)

            if not period_end_date or not disc_date_formatted:
                continue

            try:
                disc_date_obj = datetime.strptime(disc_date_formatted, "%Y-%m-%d")
                if disc_date_obj > now:
                    continue

                # 検索範囲の設定:
                # 開始: 決算短信の開示日(DiscDate)
                # 終了: min(会計期間終了日 + 97日, 現在日時)
                search_start = disc_date_obj
                search_end = min(period_end_date + timedelta(days=97), now)

                target_doc_types = [doc_type_code] if doc_type_code else (
                    ["120"] if period_type == "FY" else (
                        ["140", "160"] if period_type in ["2Q", "Q2"] else []
                    )
                )

                if not target_doc_types:
                    continue

                logger.info(f"🔍 [EDINET] Searching period={period_type}, fiscal_year={fiscal_year}, target={search_end.strftime('%Y-%m-%d')} back to {search_start.strftime('%Y-%m-%d')}")

                # 検索対象の日付リストを「新しい順（後方）」に生成
                target_dates = []
                curr = search_end
                while curr >= search_start:
                    target_dates.append(curr.strftime("%Y-%m-%d"))
                    curr -= timedelta(days=1)

                found_for_this_record = False

                # 並列で日付一覧を取得（バッチ処理）
                BATCH_SIZE = MAX_WORKERS
                for i in range(0, len(target_dates), BATCH_SIZE):
                    batch = target_dates[i:i + BATCH_SIZE]

                    batch_results = await asyncio.gather(
                        *[self._get_documents_for_date(d) for d in batch],
                        return_exceptions=True,
                    )

                    results_map: Dict[str, List[Dict[str, Any]]] = {}
                    for date_str, result in zip(batch, batch_results):
                        if isinstance(result, Exception):
                            logger.error(f"Error fetching docs for {date_str}: {result}")
                            results_map[date_str] = []
                        else:
                            results_map[date_str] = result

                    # バッチ内の日付を「新しい順」に走査してマッチング
                    for date_str in batch:
                        documents = results_map.get(date_str, [])
                        for doc in documents:
                            current_edinet_code = doc.get("edinetCode")
                            sec_code = str(doc.get("secCode", "")).strip()

                            is_match = False
                            if edinet_code and current_edinet_code == edinet_code:
                                is_match = True
                            elif sec_code.startswith(code_4digit):
                                is_match = True

                            if is_match:
                                dt = doc.get("docTypeCode", "")
                                if not target_doc_types or dt in target_doc_types:
                                    desc = doc.get("docDescription", "")
                                    if desc and ("訂正" in desc or "補正" in desc):
                                        continue

                                    logger.info(f"✨ [EDINET HIT] {sec_code}: {desc} ({date_str}) ID={doc.get('docID')}")
                                    doc["fiscal_year"] = fiscal_year
                                    doc["jquants_fy_end"] = fy_end
                                    doc["period_type"] = period_type
                                    all_documents.append(doc)
                                    found_for_this_record = True
                                    break
                        if found_for_this_record:
                            break
                    if found_for_this_record:
                        break

            except Exception as e:
                logger.error(f"❌ [EDINET] Error processing record: {e}", exc_info=True)

        # 重複除去 (docID)
        seen_ids = set()
        unique_docs = []
        for d in all_documents:
            if d["docID"] not in seen_ids:
                seen_ids.add(d["docID"])
                unique_docs.append(d)

        return unique_docs

    async def _get_documents_for_date(self, date_str: str) -> List[Dict[str, Any]]:
        """特定の日付のドキュメント一覧を取得（キャッシュ対応）"""
        cache_key = self._get_search_cache_key(date_str)
        documents = self._load_search_cache(cache_key)
        if documents is not None:
            return documents

        try:
            data = await self._request("/documents.json", {"date": date_str, "type": 2})
            documents = data.get("results", [])
            self._save_search_cache(cache_key, documents)
            return documents
        except Exception:
            return []

    async def download_document(self, doc_id: str, doc_type: int = 1, save_dir: Optional[Path] = None) -> Optional[Path]:
        """書類をダウンロード（1=XBRLのみ維持。旧2=PDFは廃止）"""
        if doc_type != 1:
            logger.warning(f"⚠️ [EDINET] ID={doc_id} の PDF ダウンロードは廃止されました。")
            return None

        if save_dir is None:
            save_dir = self.cache_dir
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        dest = save_dir / f"{doc_id}_xbrl"
        if dest.exists() and dest.is_dir():
            return dest

        if not self.api_key:
            return None

        try:
            content = await self._request_binary(f"/documents/{doc_id}", {"type": 1})
            zip_path = save_dir / f"{doc_id}.zip"
            with open(zip_path, "wb") as f:
                f.write(content)
            dest.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as z:
                for member in z.namelist():
                    member_path = (dest / member).resolve()
                    if not str(member_path).startswith(str(dest.resolve())):
                        raise ValueError(f"不正なZIPエントリ: {member}")
                z.extractall(dest)
            zip_path.unlink()
            return dest
        except Exception as e:
            logger.error(f"❌ [EDINET] XBRL Download error {doc_id}: {e}")
            return None

    async def search_recent_reports(
        self,
        code: str,
        jquants_data: List[Dict[str, Any]],
        max_years: int = 5,
        doc_types: Optional[List[str]] = None,
        max_documents: int = 10
    ) -> List[Dict[str, Any]]:
        """
        最新の財務データに基づき、直近N年分の報告書を自動検索
        """
        if not jquants_data:
            return []

        from ..utils.jquants_utils import prepare_edinet_search_data

        annual_data_idx, years_list = prepare_edinet_search_data(
            jquants_data,
            max_records=max_years * 3
        )

        years = years_list

        recent_data = [
            d for d in annual_data_idx
            if d.get("fiscal_year") in years
        ]

        return await self.search_documents(
            code=code,
            years=years,
            jquants_data=recent_data,
            doc_type_code=doc_types[0] if doc_types and len(doc_types) == 1 else None,
            max_documents=max_documents
        )

    async def fetch_latest_annual_report(self, code: str, jquants_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """最新の有価証券報告書(120)を1件取得"""
        docs = await self.search_recent_reports(code, jquants_data, max_years=10, doc_types=["120"])
        annual_reports = [d for d in docs if d.get("docTypeCode") == "120"]
        if annual_reports:
            return sorted(annual_reports, key=lambda x: x.get("submitDateTime", ""), reverse=True)[0]
        return None
