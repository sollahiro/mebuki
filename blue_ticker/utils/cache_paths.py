from pathlib import Path


def external_cache_dir(cache_dir: str | Path) -> Path:
    """外部データ取得物のキャッシュルートを返す。"""
    return Path(cache_dir) / "external"


def edinet_cache_dir(cache_dir: str | Path) -> Path:
    """EDINET API由来データのキャッシュルートを返す。"""
    return external_cache_dir(cache_dir) / "edinet"


def derived_cache_dir(cache_dir: str | Path) -> Path:
    """blue_ticker が生成した中間・分析結果キャッシュのルートを返す。"""
    return Path(cache_dir) / "derived"
