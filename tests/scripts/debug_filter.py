"""
_filter_annual_data に渡る annual_data の FY26-03 レコードの実際の値を確認する
"""
import asyncio
import json
from mebuki.api.jquants_client import JQuantsAPIClient
from mebuki.infrastructure.settings import settings_store
from mebuki.utils.financial_data import extract_annual_data
from mebuki.analysis.calculator import _filter_annual_data
from mebuki.utils.converters import is_valid_value


async def main():
    client = JQuantsAPIClient(api_key=settings_store.jquants_api_key)

    financial_data = await client.get_financial_summary(code="24320", period_types=["FY", "2Q"])
    annual_data = extract_annual_data(financial_data, include_2q=False)

    print("=== extract_annual_data の結果 (FY のみ、新しい順) ===\n")
    for r in annual_data[:6]:
        print(f"CurFYEn={r.get('CurFYEn')}  DiscDate={r.get('DiscDate')}  CurPerType={r.get('CurPerType')}")
        print(f"  Sales={r.get('Sales')!r}  OP={r.get('OP')!r}  NP={r.get('NP')!r}  Eq={r.get('Eq')!r}")
        print(f"  is_valid_value(Sales)={is_valid_value(r.get('Sales'))}  is_valid_value(OP)={is_valid_value(r.get('OP'))}")
        print()

    print("=== _filter_annual_data(annual_data, 5) の結果 ===\n")
    filtered = _filter_annual_data(annual_data, 5)
    for r in filtered:
        print(f"CurFYEn={r.get('CurFYEn')}  CurPerType={r.get('CurPerType')}  Sales={r.get('Sales')!r}")


if __name__ == "__main__":
    asyncio.run(main())
