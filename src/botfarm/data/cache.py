"""Local disk cache for Bitget candle history, so repeated backtests don't
re-hit the API for date ranges already fetched."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .bitget_client import BitgetPublicClient, Candle

CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"

CANDLE_COLUMNS = [
    "ts_ms", "open", "high", "low", "close",
    "base_volume", "quote_volume", "usdt_volume",
]


def _cache_path(symbol: str, granularity: str) -> Path:
    return CACHE_DIR / f"{symbol}_{granularity}.csv.gz"


def _candles_to_df(candles: list[Candle]) -> pd.DataFrame:
    if not candles:
        return pd.DataFrame(columns=CANDLE_COLUMNS)
    df = pd.DataFrame([c.__dict__ for c in candles], columns=CANDLE_COLUMNS)
    return df.sort_values("ts_ms").drop_duplicates("ts_ms").reset_index(drop=True)


def load_cached(symbol: str, granularity: str) -> pd.DataFrame:
    path = _cache_path(symbol, granularity)
    if not path.exists():
        return pd.DataFrame(columns=CANDLE_COLUMNS)
    return pd.read_csv(path)


def save_cache(symbol: str, granularity: str, df: pd.DataFrame) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(symbol, granularity)
    df.sort_values("ts_ms").drop_duplicates("ts_ms").to_csv(path, index=False)


def get_or_fetch(
    client: BitgetPublicClient,
    symbol: str,
    granularity: str,
    start_ms: int,
    end_ms: int,
) -> pd.DataFrame:
    """Return candles covering [start_ms, end_ms], fetching only the gap
    between what's cached and what's requested."""
    cached = load_cached(symbol, granularity)

    if cached.empty:
        fetched = client.fetch_full_history(symbol, granularity, start_ms, end_ms)
        df = _candles_to_df(fetched)
        save_cache(symbol, granularity, df)
        return df[(df.ts_ms >= start_ms) & (df.ts_ms <= end_ms)].reset_index(drop=True)

    cached_min, cached_max = int(cached.ts_ms.min()), int(cached.ts_ms.max())
    new_frames = [cached]

    if start_ms < cached_min:
        older = client.fetch_full_history(symbol, granularity, start_ms, cached_min - 1)
        new_frames.append(_candles_to_df(older))

    if end_ms > cached_max:
        newer = client.fetch_full_history(symbol, granularity, cached_max + 1, end_ms)
        new_frames.append(_candles_to_df(newer))

    merged = pd.concat(new_frames, ignore_index=True)
    merged = merged.sort_values("ts_ms").drop_duplicates("ts_ms").reset_index(drop=True)
    save_cache(symbol, granularity, merged)
    return merged[(merged.ts_ms >= start_ms) & (merged.ts_ms <= end_ms)].reset_index(drop=True)
