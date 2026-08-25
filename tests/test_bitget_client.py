from unittest.mock import MagicMock, patch

import pytest

from botfarm.data.bitget_client import BitgetAPIError, BitgetPublicClient


def _mock_response(payload, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    resp.raise_for_status = MagicMock()
    return resp


def _sample_row(ts_ms):
    return [str(ts_ms), "50000.0", "50100.0", "49900.0", "50050.0", "1.5", "75075.0", "75075.0"]


def test_get_candles_parses_and_sorts():
    client = BitgetPublicClient()
    rows = [_sample_row(2000), _sample_row(1000)]
    payload = {"code": "00000", "msg": "success", "data": rows}
    with patch.object(client._session, "get", return_value=_mock_response(payload)):
        candles = client.get_candles(symbol="BTCUSDT", granularity="5min")
    assert [c.ts_ms for c in candles] == [1000, 2000]
    assert candles[0].close == pytest.approx(50050.0)


def test_invalid_granularity_raises():
    client = BitgetPublicClient()
    with pytest.raises(ValueError):
        client.get_candles(granularity="7min")


def test_api_error_code_raises_after_retries():
    client = BitgetPublicClient()
    payload = {"code": "40001", "msg": "bad request", "data": []}
    with patch.object(client._session, "get", return_value=_mock_response(payload)):
        with patch("time.sleep"):
            with pytest.raises(BitgetAPIError):
                client.get_candles(granularity="5min")


def test_fetch_full_history_paginates_backward():
    client = BitgetPublicClient()
    # Two pages: newest page [3000,4000], then older page [1000,2000]; then empty.
    page1 = {"code": "00000", "msg": "success", "data": [_sample_row(3000), _sample_row(4000)]}
    page2 = {"code": "00000", "msg": "success", "data": [_sample_row(1000), _sample_row(2000)]}
    page3 = {"code": "00000", "msg": "success", "data": []}
    responses = [_mock_response(page1), _mock_response(page2), _mock_response(page3)]
    with patch.object(client._session, "get", side_effect=responses):
        candles = client.fetch_full_history("BTCUSDT", "5min", start_ms=1000, end_ms=4000)
    assert [c.ts_ms for c in candles] == [1000, 2000, 3000, 4000]
