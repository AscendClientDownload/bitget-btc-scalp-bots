"""Client for Bitget's public spot market-data REST API.

No authentication is used or required — only public candlestick endpoints.
No order-placement methods exist here or anywhere in this project.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import requests

BASE_URL = "https://api.bitget.com"
CANDLES_PATH = "/api/v2/spot/market/candles"
HISTORY_CANDLES_PATH = "/api/v2/spot/market/history-candles"

VALID_GRANULARITIES = {"1min", "5min"}

# Confirmed empirically 2026-08-25: /candles accepts limit up to 1000, but
# /history-candles rejects anything above 200 with code 40020 "Parameter
# limit error" — the two endpoints have different caps despite sharing a
# `limit` param name.
HISTORY_CANDLES_MAX_LIMIT = 200

MAX_RETRIES = 5
RETRY_BACKOFF_BASE_SECONDS = 0.5
REQUEST_THROTTLE_SECONDS = 0.2


@dataclass(frozen=True)
class Candle:
    ts_ms: int
    open: float
    high: float
    low: float
    close: float
    base_volume: float
    quote_volume: float
    usdt_volume: float


class BitgetAPIError(RuntimeError):
    pass


class BitgetPublicClient:
    """Thin wrapper around Bitget's public spot candlestick endpoints."""

    def __init__(self, session: requests.Session | None = None, base_url: str = BASE_URL):
        self._session = session or requests.Session()
        self._base_url = base_url
        self._last_request_time = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < REQUEST_THROTTLE_SECONDS:
            time.sleep(REQUEST_THROTTLE_SECONDS - elapsed)

    def _get(self, path: str, params: dict) -> list:
        if params.get("granularity") not in VALID_GRANULARITIES:
            raise ValueError(f"granularity must be one of {VALID_GRANULARITIES}")

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            self._throttle()
            self._last_request_time = time.monotonic()
            try:
                resp = self._session.get(f"{self._base_url}{path}", params=params, timeout=10)
                self._last_request_time = time.monotonic()
                if resp.status_code == 429:
                    raise BitgetAPIError(f"rate limited (HTTP 429) on {path}")
                resp.raise_for_status()
                payload = resp.json()
                if payload.get("code") != "00000":
                    raise BitgetAPIError(f"Bitget API error: {payload.get('code')} {payload.get('msg')}")
                return payload.get("data", [])
            except (requests.RequestException, BitgetAPIError) as exc:
                last_error = exc
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF_BASE_SECONDS * (2 ** attempt))
        raise BitgetAPIError(f"failed after {MAX_RETRIES} attempts: {last_error}") from last_error

    @staticmethod
    def _parse_rows(rows: list) -> list[Candle]:
        candles = [
            Candle(
                ts_ms=int(r[0]),
                open=float(r[1]),
                high=float(r[2]),
                low=float(r[3]),
                close=float(r[4]),
                base_volume=float(r[5]),
                quote_volume=float(r[6]),
                usdt_volume=float(r[7]),
            )
            for r in rows
        ]
        candles.sort(key=lambda c: c.ts_ms)
        # Defensive de-dupe by timestamp (API documented as ascending/unique,
        # but pagination boundaries make an off-by-one duplicate plausible).
        deduped: dict[int, Candle] = {c.ts_ms: c for c in candles}
        return [deduped[ts] for ts in sorted(deduped)]

    def get_candles(
        self,
        symbol: str = "BTCUSDT",
        granularity: str = "5min",
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 1000,
    ) -> list[Candle]:
        """Recent candles (bounded by what Bitget retains for this endpoint)."""
        params = {"symbol": symbol, "granularity": granularity, "limit": limit}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        return self._parse_rows(self._get(CANDLES_PATH, params))

    def get_history_candles(
        self,
        symbol: str = "BTCUSDT",
        granularity: str = "5min",
        end_time: int | None = None,
        limit: int = HISTORY_CANDLES_MAX_LIMIT,
    ) -> list[Candle]:
        """Older candles, paginated backward from end_time."""
        limit = min(limit, HISTORY_CANDLES_MAX_LIMIT)
        params = {"symbol": symbol, "granularity": granularity, "limit": limit}
        if end_time is not None:
            params["endTime"] = end_time
        return self._parse_rows(self._get(HISTORY_CANDLES_PATH, params))

    def fetch_full_history(
        self,
        symbol: str,
        granularity: str,
        start_ms: int,
        end_ms: int,
        limit: int = HISTORY_CANDLES_MAX_LIMIT,
    ) -> list[Candle]:
        """Walk history-candles backward from end_ms until start_ms is covered."""
        all_candles: dict[int, Candle] = {}
        cursor_end = end_ms

        while True:
            page = self.get_history_candles(
                symbol=symbol, granularity=granularity, end_time=cursor_end, limit=limit
            )
            if not page:
                break

            new_page = [c for c in page if c.ts_ms not in all_candles]
            for c in page:
                all_candles[c.ts_ms] = c

            oldest_ts = min(c.ts_ms for c in page)
            if oldest_ts <= start_ms:
                break
            if not new_page:
                # No forward progress (API returned an already-seen page) — stop
                # rather than loop forever.
                break

            cursor_end = oldest_ts - 1

        result = sorted(all_candles.values(), key=lambda c: c.ts_ms)
        return [c for c in result if start_ms <= c.ts_ms <= end_ms]
