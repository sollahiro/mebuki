"""
J-QUANTS + EDINET 並列化の効果をシミュレーションで計測する。
asyncio.sleep で実際のAPIレイテンシを再現し、before/after の実行時間を比較する。

Usage:
    python tests/scripts/benchmark_parallelization.py
"""
import asyncio
import time

# 代表的なレイテンシ（秒）
T_JQUANTS = 2.0        # J-QUANTS fetch（内部は master + financial_summary で並列済）
T_CALC = 0.001         # calculate_metrics（CPU計算のみ）
T_PREDOWNLOAD = 12.0   # predownload_and_parse（5年分XBRL DL）
T_FETCH_EDINET = 2.5   # fetch_edinet_data_async（EDINET書類メタ検索）
T_EXTRACT_ALL = 1.5    # extract_all_by_year（pre_parsed使用時、CPU主体）


async def _fetch_financial_data():
    await asyncio.sleep(T_JQUANTS)
    return "financial_data", "annual_data"


async def _calculate_metrics(annual_data):
    await asyncio.sleep(T_CALC)
    return "metrics"


async def _predownload_and_parse(financial_data):
    await asyncio.sleep(T_PREDOWNLOAD)
    return "pre_parsed_map"


async def _fetch_edinet_data_async(financial_data):
    await asyncio.sleep(T_FETCH_EDINET)
    return "edinet_data"


async def _extract_all_by_year(financial_data, pre_parsed_map):
    await asyncio.sleep(T_EXTRACT_ALL)
    return "all_metrics"


async def run_before():
    """変更前: predownload → [fetch_edinet + extract_all]（fetch_edinet は直列）"""
    financial_data, annual_data = await _fetch_financial_data()
    metrics = await _calculate_metrics(annual_data)
    pre_parsed_map = await _predownload_and_parse(financial_data)
    edinet_data, all_metrics = await asyncio.gather(
        _fetch_edinet_data_async(financial_data),
        _extract_all_by_year(financial_data, pre_parsed_map),
    )
    return metrics, edinet_data, all_metrics


async def run_after():
    """変更後: [predownload + fetch_edinet] → extract_all（fetch_edinet を並列化）"""
    financial_data, annual_data = await _fetch_financial_data()
    metrics = await _calculate_metrics(annual_data)
    pre_parsed_map, edinet_data = await asyncio.gather(
        _predownload_and_parse(financial_data),
        _fetch_edinet_data_async(financial_data),
    )
    all_metrics = await _extract_all_by_year(financial_data, pre_parsed_map)
    return metrics, edinet_data, all_metrics


def measure(label, coro_fn) -> float:
    t0 = time.perf_counter()
    asyncio.run(coro_fn())
    elapsed = time.perf_counter() - t0
    print(f"  {label}: {elapsed:.2f}s")
    return elapsed


def main():
    print("=== 並列化効果シミュレーション（APIレイテンシを sleep で再現） ===\n")
    print("想定レイテンシ:")
    print(f"  J-QUANTS fetch:      {T_JQUANTS:.1f}s")
    print(f"  calculate_metrics:   {T_CALC * 1000:.0f}ms")
    print(f"  predownload_parse:   {T_PREDOWNLOAD:.1f}s  ← XBRL 5件DL")
    print(f"  fetch_edinet_data:   {T_FETCH_EDINET:.1f}s  ← 書類メタ検索")
    print(f"  extract_all_by_year: {T_EXTRACT_ALL:.1f}s  ← CPU主体")
    print()

    print("実行時間:")
    t_before = measure("Before", run_before)
    t_after  = measure("After ", run_after)

    saved = t_before - t_after
    print(f"\n削減: {saved:.2f}s ({saved / t_before * 100:.0f}%)")


if __name__ == "__main__":
    main()
