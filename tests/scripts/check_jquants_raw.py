"""
J-Quants API の生レスポンスを確認するスクリプト
2432 (DeNA) の financial_summary を取得して FY26-03 レコードの中身を調べる
"""
import asyncio
import json
from mebuki.api.jquants_client import JQuantsAPIClient
from mebuki.infrastructure.settings import settings_store


async def main():
    client = JQuantsAPIClient(api_key=settings_store.jquants_api_key)

    print("=== /fins/summary for 2432 (raw) ===\n")
    data = await client.get_financial_summary(code="24320")

    # CurFYEn で降順ソートして直近 5 件表示
    sorted_data = sorted(data, key=lambda x: x.get("CurFYEn", ""), reverse=True)

    for record in sorted_data[:8]:
        print(json.dumps(record, ensure_ascii=False, indent=2))
        print("-" * 60)


if __name__ == "__main__":
    asyncio.run(main())
