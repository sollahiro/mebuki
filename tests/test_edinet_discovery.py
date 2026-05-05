from datetime import date
from unittest.mock import Mock

import pytest

from mebuki.utils import edinet_discovery


@pytest.mark.asyncio
async def test_find_half_report_accepts_160_with_fy_period_end(monkeypatch) -> None:
    async def fake_fetch(_client, _start: date, _end: date):
        return {
            "2024-11-12": [{
                "docID": "S100UOCS",
                "secCode": "28020",
                "docTypeCode": "160",
                "docDescription": "半期報告書－第147期(2024/04/01－2025/03/31)",
                "periodStart": "2024-04-01",
                "periodEnd": "2025-03-31",
                "submitDateTime": "2024-11-12 13:08",
            }]
        }

    monkeypatch.setattr(edinet_discovery, "_fetch_date_range_cached", fake_fetch)

    doc = await edinet_discovery._find_half_report_for_fy(
        "28020",
        date(2024, 4, 1),
        date(2025, 3, 31),
        Mock(),
    )

    assert doc is not None
    assert doc["docID"] == "S100UOCS"
    assert doc["edinet_fy_end"] == "2025-03-31"
    assert doc["edinet_period_start"] == "2024-04-01"
    assert doc["edinet_period_end"] == "2024-09-30"
    assert doc["period_type"] == "2Q"


@pytest.mark.asyncio
async def test_find_half_report_accepts_legacy_140_with_q2_period_end(monkeypatch) -> None:
    async def fake_fetch(_client, _start: date, _end: date):
        return {
            "2023-11-09": [{
                "docID": "S100S3PK",
                "secCode": "28020",
                "docTypeCode": "140",
                "docDescription": "四半期報告書－第146期第2四半期(2023/07/01－2023/09/30)",
                "periodStart": "2023-07-01",
                "periodEnd": "2023-09-30",
                "submitDateTime": "2023-11-09 14:57",
            }]
        }

    monkeypatch.setattr(edinet_discovery, "_fetch_date_range_cached", fake_fetch)

    doc = await edinet_discovery._find_half_report_for_fy(
        "28020",
        date(2023, 4, 1),
        date(2024, 3, 31),
        Mock(),
    )

    assert doc is not None
    assert doc["docID"] == "S100S3PK"
    assert doc["edinet_fy_end"] == "2024-03-31"
    assert doc["edinet_period_start"] == "2023-04-01"
    assert doc["edinet_period_end"] == "2023-09-30"
    assert doc["period_type"] == "2Q"
