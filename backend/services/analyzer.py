"""
個別詳細分析モジュール

個別銘柄の詳細分析を実行します。
"""

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable, AsyncGenerator
from datetime import datetime
from pathlib import Path

from mebuki.api.jquants_client import JQuantsAPIClient
from mebuki.utils.financial_data import extract_annual_data
from mebuki.analysis.calculator import calculate_metrics_flexible
from mebuki.utils.jquants_utils import prepare_edinet_search_data
from mebuki.api.edinet_client import EdinetAPIClient
from mebuki.analysis.xbrl_parser import XBRLParser
from mebuki.utils.cache import CacheManager

from backend.settings import settings_store

logger = logging.getLogger(__name__)




class IndividualAnalyzer:
    """個別詳細分析クラス"""
    
    def __init__(
        self,
        api_client: Optional[JQuantsAPIClient] = None,
        edinet_client: Optional['EdinetAPIClient'] = None,
        cache: Optional[CacheManager] = None,
        use_cache: bool = True
    ):
        """
        初期化
        
        Args:
            api_client: J-QUANTS APIクライアント。Noneの場合は新規作成
            edinet_client: EDINET APIクライアント。Noneの場合は新規作成
            cache: キャッシュマネージャー。Noneの場合は新規作成
            use_cache: キャッシュを使用するか
        """
        self.api_client = api_client or JQuantsAPIClient(api_key=settings_store.jquants_api_key)
        self.use_cache = use_cache
        self.cache = cache if cache is not None else (
            CacheManager(
                cache_dir=settings_store.cache_dir,
                enabled=settings_store.cache_enabled
            ) if use_cache else None
        )
        
        # EDINET統合
        if edinet_client is not None:
            self.edinet_client = edinet_client
        else:
            try:
                # EDINETの検索用キャッシュも永続領域へ
                edinet_cache_dir = Path(settings_store.cache_dir) / "edinet"
                self.edinet_client = EdinetAPIClient(
                    api_key=settings_store.edinet_api_key,
                    cache_dir=str(edinet_cache_dir)
                )
            except Exception as e:
                logger.warning(f"EDINETクライアントの初期化に失敗しました: {e}")
                self.edinet_client = None
        
        # XBRLパーサーは常に初期化
        try:
            self.xbrl_parser = XBRLParser()
        except Exception as e:
            logger.warning(f"XBRLパーサーの初期化に失敗しました: {e}")
            self.xbrl_parser = None
    
    def _fetch_financial_data(
        self,
        code: str
    ) -> tuple[Optional[Dict[str, Any]], Optional[List[Dict[str, Any]]], Optional[List[Dict[str, Any]]]]:
        """財務データを取得"""
        master_data = self.api_client.get_equity_master(code=code)
        stock_info = master_data[0] if master_data else {}
        
        if not stock_info:
            logger.warning(f"銘柄コード {code}: 銘柄マスタにデータが見つかりませんでした。")
            return None, None, None
        
        financial_data = self.api_client.get_financial_summary(
            code=code,
            period_types=["FY", "2Q"],
            include_fields=None
        )
        
        if not financial_data:
            logger.warning(f"銘柄コード {code}: 財務データが取得できませんでした。")
            return stock_info, None, None
        
        try:
            annual_data = extract_annual_data(financial_data)
        except Exception as e:
            logger.error(f"銘柄コード {code}: 年度データ抽出中にエラーが発生しました - {e}", exc_info=True)
            return stock_info, financial_data, None
        
        return stock_info, financial_data, annual_data
    
    def _fetch_prices(
        self,
        code: str,
        annual_data: List[Dict[str, Any]],
        analysis_years: int
    ) -> Dict[str, float]:
        """年度末株価を取得"""
        prices = {}
        subscription_start_date = datetime(2021, 1, 9)
        dates_to_fetch = []
        date_to_fy_end = {}
        
        for year_data in annual_data[:analysis_years]:
            fy_end = year_data.get("CurFYEn")
            if fy_end:
                if len(fy_end) == 8:
                    fy_end_formatted = f"{fy_end[:4]}-{fy_end[4:6]}-{fy_end[6:8]}"
                else:
                    fy_end_formatted = fy_end[:10] if len(fy_end) >= 10 else fy_end
                
                try:
                    fy_end_date = datetime.strptime(fy_end, "%Y%m%d") if len(fy_end) == 8 else datetime.strptime(fy_end[:10], "%Y-%m-%d")
                    if fy_end_date and fy_end_date < subscription_start_date:
                        continue
                    
                    dates_to_fetch.append(fy_end_formatted)
                    date_to_fy_end[fy_end_formatted] = fy_end
                except (ValueError, TypeError):
                    pass
        
        if dates_to_fetch:
            try:
                batch_prices = self.api_client.get_prices_at_dates(code, dates_to_fetch, use_nearest_trading_day=True)
                for date_str, price in batch_prices.items():
                    if price is not None:
                        prices[date_str] = price
                        original = date_to_fy_end.get(date_str)
                        if original:
                            prices[original] = price
            except Exception as e:
                logger.warning(f"バッチ株価取得に失敗、個別取得にフォールバック: {e}")
                for date_str in dates_to_fetch:
                    try:
                        price = self.api_client.get_price_at_date(code, date_str, use_nearest_trading_day=True)
                        if price:
                            prices[date_str] = price
                    except:
                        pass
        return prices
    
    def _calculate_metrics(
        self,
        code: str,
        annual_data: List[Dict[str, Any]],
        prices: Dict[str, float],
        analysis_years: int
    ) -> Optional[Dict[str, Any]]:
        """指標を計算"""
        try:
            return calculate_metrics_flexible(annual_data, prices, analysis_years)
        except Exception as e:
            logger.error(f"銘柄コード {code}: 指標計算中にエラーが発生しました - {e}", exc_info=True)
            return None
    
    
    def _fetch_edinet_data(
        self,
        code: str,
        financial_data: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None,
        max_documents: int = 10
    ) -> Dict[int, Any]:
        """EDINETデータを取得"""
        if not self.edinet_client:
            return {}
        try:
            master_data = self.api_client.get_equity_master(code=code)
            edinet_code = master_data[0].get("EdinetCode") if master_data else None
            # max_records=6はJ-QUANTSレコード数。見つかる書類数は max_documents で制限。
            annual_data_idx, years_list = prepare_edinet_search_data(financial_data, max_records=max_documents * 2 + 2)
            return self.fetch_edinet_reports(code, years_list, jquants_annual_data=annual_data_idx, progress_callback=progress_callback, edinet_code=edinet_code, max_documents=max_documents)
        except Exception as e:
            logger.error(f"EDINETデータ取得エラー: {code} - {e}", exc_info=True)
            return {}


    async def analyze_stock_stream(self, code: str) -> AsyncGenerator[Dict[str, Any], None]:
        """銘柄分析をストリーミング形式で実行（並列化版）"""
        cache_key = f"individual_analysis_{code}"
        
        # 1. キャッシュチェック
        if self.use_cache and self.cache:
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                cached_result["status"] = "complete"
                cached_result["message"] = "分析完了（キャッシュ）"
                yield cached_result
                return
        # 共有される結果オブジェクト
        result = {
            "code": code,
            "status": "initializing",
            "message": "銘柄データを取得中...",
            "analyzed_at": datetime.now().isoformat(),
        }
        
        queue = asyncio.Queue()

        async def main_flow():
            """メインフロー: 財務 -> 株価 -> LLM"""
            try:
                # 財務データ取得
                stock_info, financial_data, annual_data = await asyncio.to_thread(self._fetch_financial_data, code)
                if not stock_info or not financial_data or not annual_data:
                    await queue.put({"status": "error", "message": "財務データの取得に失敗しました"})
                    return
                
                # 基本情報を反映
                result.update({
                    "name": stock_info.get("CoName"),
                    "name_en": stock_info.get("CoNameEn"),
                    "sector_33_name": stock_info.get("S33Nm"),
                    "market_name": stock_info.get("MktNm"),
                })
                
                # 指標計算 (第1段階: 株価なし)
                available_years = len(annual_data)
                max_years = settings_store.get_max_analysis_years()
                analysis_years = min(available_years, max_years)
                
                metrics = await asyncio.to_thread(self._calculate_metrics, code, annual_data, None, analysis_years)
                if metrics:
                    result["metrics"] = metrics
                    result["status"] = "fetching_prices"
                    result["message"] = "株価と有価証券報告書を取得・解析中..."
                    await queue.put(result.copy())
                
                # 株価取得とEDINETデータ検索を並列で開始
                # EDINETフローはタスクとして生成し、株価取得はgatherで並行実行
                async def fetch_prices_and_setup_edinet():
                    prices_task = asyncio.to_thread(self._fetch_prices, code, annual_data, analysis_years)
                    # search_documentsはEDINETフローの中で呼ばれるため、ここでは株価取得を優先つつgather
                    return await prices_task

                edinet_code = stock_info.get("EdinetCode")
                edinet_task = asyncio.create_task(edinet_flow(financial_data, edinet_code))
                prices = await fetch_prices_and_setup_edinet()
                metrics = await asyncio.to_thread(self._calculate_metrics, code, annual_data, prices, analysis_years)
                
                if metrics:
                    result["metrics"] = metrics
                    result["status"] = "fetching_edinet"
                    result["message"] = "有価証券報告書を取得中..."
                    await queue.put(result.copy())
                else:
                    await queue.put({"status": "error", "message": "株価反映後の指標計算に失敗しました"})
                    return


                # メインフロー完了
                result["status"] = "fetching_edinet"
                result["message"] = "有価証券報告書を取得中..."
                await queue.put(result.copy())

                await edinet_task
                
                # 最終結果をキャッシュに保存
                result["status"] = "complete"
                result["message"] = "分析完了"
                if self.cache:
                    self.cache.set(cache_key, result.copy())
                await queue.put(result.copy())

            except Exception as e:
                logger.error(f"メインフローエラー: {e}", exc_info=True)
                await queue.put({"status": "error", "message": str(e)})

        async def edinet_flow(financial_data, edinet_code=None):
            """EDINETフロー: 書類取得 -> 要約 (ストリーミング)"""
            try:
                async for data in self.fetch_edinet_reports_stream(code, financial_data, edinet_code=edinet_code):
                    fy_key = data["fy_key"]
                    report = data["report"]
                    
                    if "edinet_data" not in result:
                        result["edinet_data"] = {}
                    
                    # 互換性のために文字列キーを使用
                    fy_key_str = str(fy_key)
                    if fy_key_str not in result["edinet_data"]:
                        result["edinet_data"][fy_key_str] = []
                    
                    # 既存のレポートを更新または追加
                    found = False
                    for i, existing in enumerate(result["edinet_data"][fy_key_str]):
                        if existing["docID"] == report["docID"]:
                            result["edinet_data"][fy_key_str][i] = report
                            found = True
                            break
                    if not found:
                        result["edinet_data"][fy_key_str].append(report)
                    
                    # 準備ができた情報を都度送信
                    await queue.put(result.copy())
            except Exception as e:
                logger.error(f"EDINETフローエラー: {e}", exc_info=True)
                # EDINETのエラーはメインの妨げにしない

        # 実行開始
        main_task = asyncio.create_task(main_flow())
        
        try:
            # 初回通知
            yield result

            finished = False
            while not finished:
                try:
                    # タイムアウト付きでキューから取得（終了判定のため）
                    item = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield item
                    
                    if item.get("status") in ["complete", "error"]:
                        finished = True
                    
                except asyncio.TimeoutError:
                    if main_task.done():
                        # タスクが終了しているのにキューが空なら終了
                        if queue.empty():
                            finished = True
                    continue
                except Exception as e:
                    logger.error(f"配信ループエラー: {e}")
                    finished = True
        finally:
            # 接続が切れた場合や終了した場合、実行中のタスクを確実にキャンセルする
            if not main_task.done():
                logger.info(f"分析タスクをキャンセルします: {code}")
                main_task.cancel()
                try:
                    await main_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"タスクキャンセル中のエラー: {e}")

    async def analyze_stock(self, code: str, progress_callback: Optional[Callable] = None) -> Optional[Dict[str, Any]]:
        """個別銘柄を詳細分析"""
        cache_key = f"individual_analysis_{code}"
        
        if self.use_cache and self.cache:
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                return cached_result

        try:
            # 1. 財務データ取得
            stock_info, financial_data, annual_data = await asyncio.to_thread(self._fetch_financial_data, code)
            if not stock_info or not financial_data or not annual_data:
                return None
            
            # 2. 指標計算
            available_years = len(annual_data)
            max_years = settings_store.get_max_analysis_years()
            analysis_years = min(available_years, max_years)
            
            prices = await asyncio.to_thread(self._fetch_prices, code, annual_data, analysis_years)
            metrics = await asyncio.to_thread(self._calculate_metrics, code, annual_data, prices, analysis_years)
            if not metrics:
                return None
            
            # 3. 結果の作成
            result = {
                "code": code,
                "name": stock_info.get("CoName"),
                "name_en": stock_info.get("CoNameEn"),
                "sector_33_name": stock_info.get("S33Nm"),
                "market_name": stock_info.get("MktNm"),
                "metrics": metrics,
                "analyzed_at": datetime.now().isoformat(),
            }
            
            edinet_data = await asyncio.to_thread(self._fetch_edinet_data, code, financial_data, progress_callback)
            if edinet_data:
                result["edinet_data"] = edinet_data
            
            # 5. 保存とキャッシュ
            if self.cache:
                self.cache.set(cache_key, result)
            
            return result
        except Exception as e:
            logger.error(f"エラー: {code} の分析に失敗しました: {e}", exc_info=True)
            return None

    async def fetch_edinet_reports_stream(
        self,
        code: str,
        financial_data: List[Dict[str, Any]],
        max_documents: int = 20,
        edinet_code: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        EDINET書類を取得し、準備ができた段階で順次yieldする（PDF優先・要約後続）
        """
        if not self.edinet_client or not self.edinet_client.api_key:
            logger.warning(f"EDINETクライアントが利用不可またはAPIキー未設定: code={code}")
            return

        try:
            # 検索データの準備
            if not edinet_code:
                master_data = await asyncio.to_thread(self.api_client.get_equity_master, code=code)
                edinet_code = master_data[0].get("EdinetCode") if master_data else None
            
            # 余裕を持って検索（ただし取得件数は max_documents で制限）
            annual_data_idx, years_list = prepare_edinet_search_data(financial_data, max_records=max_documents * 3)
            
            # 1. 書類を検索・特定
            reports_dir = Path(settings_store.reports_dir) / f"{code}_edinet"
            all_docs = await asyncio.to_thread(
                self.edinet_client.search_documents,
                code,
                years=years_list,
                jquants_data=annual_data_idx,
                edinet_code=edinet_code,
                max_documents=max_documents
            )
            
            if not all_docs:
                logger.info(f"EDINET書類が見つかりませんでした: code={code}")
                return

            # 日付順（新しい順）にソート
            all_docs.sort(key=lambda x: x.get("submitDateTime", ""), reverse=True)

            # 2. 各書類の本体(PDF/XBRL)を順次ダウンロードして即座にyield
            reports_with_paths = []
            for doc in all_docs:
                doc_id = doc["docID"]
                dt = doc.get("docTypeCode")
                label = "有価証券報告書" if dt == "120" else "半期報告書"
                year = doc.get("fiscal_year")
                fy_key = doc.get("jquants_fy_end") or str(year) # フォールバック

                # PDFのみダウンロード（要約は廃止）
                pdf_path = await asyncio.to_thread(self.edinet_client.download_document, doc_id, 2, reports_dir)

                report_info = {
                    "docID": doc_id,
                    "submitDate": doc.get("submitDateTime", "")[:10],
                    "pdf_path": str(pdf_path) if pdf_path else None,
                    "xbrl_path": None, # XBRLは不要になったため
                    "edinetCode": doc.get("edinetCode"),
                    "docType": label,
                    "docTypeCode": dt,
                    "fiscal_year": year,
                    "jquants_fy_end": fy_key
                }
                
                # PDF情報の準備ができたものから即座に通知
                yield {"year": year, "fy_key": fy_key, "report": report_info}

        except Exception as e:
            logger.error(f"EDINETストリーミング取得エラー: {code} - {e}", exc_info=True)

    def fetch_edinet_reports(
        self,
        code: str,
        years: List[int],
        jquants_annual_data: Optional[List[Dict[str, Any]]] = None,
        progress_callback: Optional[Callable] = None,
        edinet_code: Optional[str] = None,
        max_documents: int = 20
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        指定年度の有価証券報告書を取得し、要約を生成（同期互換用）
        """
        # 注意: 非同期ジェネレータを同期的に回すためにイベントループを使用
        # analyzerクラス内での同期呼び出し用
        results = {}
        
        async def _run():
            async for data in self.fetch_edinet_reports_stream(code, jquants_annual_data, max_documents):
                fy_key = data["fy_key"]
                report = data["report"]
                # 互換性のために文字列キーを使用
                fy_key_str = str(fy_key)
                if fy_key_str not in results:
                    results[fy_key_str] = []
                
                # 既存のレポートを更新または追加
                found = False
                for i, existing in enumerate(results[fy_key_str]):
                    if existing["docID"] == report["docID"]:
                        results[fy_key_str][i] = report
                        found = True
                        break
                if not found:
                    results[fy_key_str].append(report)
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if loop.is_running():
            # すでにループが走っている場合は、このメソッド自体も非同期呼び出しされるべきだが、
            # 暫定的にスレッドで回すか、呼び出し側を修正する必要がある。
            # 現在の analyzer.py の中では to_thread で呼ばれているので、新規ループで実行。
            import threading
            def run_in_new_loop():
                new_loop = asyncio.new_event_loop()
                new_loop.run_until_complete(_run())
                new_loop.close()
            t = threading.Thread(target=run_in_new_loop)
            t.start()
            t.join()
        else:
            loop.run_until_complete(_run())
            
        return results



    async def retry_edinet_fetch(self, code: str) -> AsyncGenerator[Dict[str, Any], None]:
        """EDINET書類取得のみを再試行"""
        cache_key = f"individual_analysis_{code}"
        result = self.cache.get(cache_key) if self.cache else None
        
        if not result:
            yield {"status": "error", "message": "キャッシュデータが見つかりません。"}
            return

        try:
            # 財務データが必要（EDINET検索用）
            # 注意: analyzer._fetch_financial_data は asyncio.to_thread で呼ぶ必要がある
            stock_info, financial_data, annual_data = await asyncio.to_thread(self._fetch_financial_data, code)
            
            if not financial_data:
                yield {"status": "error", "message": "EDINET検索に必要な財務情報が取得できませんでした。"}
                return

            result["status"] = "fetching_edinet"
            result["message"] = "有価証券報告書を再取得中..."
            yield result.copy()

            edinet_data = await asyncio.to_thread(self._fetch_edinet_data, code, financial_data, max_documents=10)
            if edinet_data:
                result["edinet_data"] = edinet_data
            
            result["status"] = "complete"
            result["message"] = "EDINET取得完了"
            if self.cache:
                self.cache.set(cache_key, result)
            yield result.copy()

        except Exception as e:
            logger.error(f"EDINET再取得エラー: {e}", exc_info=True)
            yield {"status": "error", "message": str(e)}


# 互換性維持
# パターン評価関数は patterns.py に移動済み
