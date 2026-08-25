import pytest

from botfarm.catalog.schema import (
    VALID_CATEGORIES,
    SpecValidationError,
    load_all_specs,
    spec_from_dict,
)

VALID_SPEC = {
    "id": "test_spec_001",
    "name": "Test Spec",
    "category": "mean_reversion",
    "timeframe": "5min",
    "indicators": [{"name": "rsi", "alias": "rsi_14", "params": {"period": 14}}],
    "entry": {"side": "long", "rule": "rsi_14 < 30"},
    "exit": {"rule": "rsi_14 > 55"},
    "atr_period": 14,
    "stop_loss_atr_mult": 1.5,
    "take_profit_atr_mult": 2.5,
    "max_holding_bars": 24,
}


def test_valid_spec_parses():
    spec = spec_from_dict(VALID_SPEC)
    assert spec.id == "test_spec_001"
    assert spec.category == "mean_reversion"
    assert len(spec.indicators) == 1


def test_invalid_category_rejected():
    bad = dict(VALID_SPEC, category="not_a_real_category")
    with pytest.raises(SpecValidationError):
        spec_from_dict(bad)


def test_invalid_timeframe_rejected():
    bad = dict(VALID_SPEC, timeframe="15min")
    with pytest.raises(SpecValidationError):
        spec_from_dict(bad)


def test_short_side_rejected():
    bad = dict(VALID_SPEC, entry={"side": "short", "rule": "rsi_14 < 30"})
    with pytest.raises(SpecValidationError):
        spec_from_dict(bad)


def test_negative_atr_multiple_rejected():
    bad = dict(VALID_SPEC, stop_loss_atr_mult=-1.0)
    with pytest.raises(SpecValidationError):
        spec_from_dict(bad)


def test_missing_required_field_rejected():
    bad = {k: v for k, v in VALID_SPEC.items() if k != "atr_period"}
    with pytest.raises(SpecValidationError):
        spec_from_dict(bad)


def test_full_catalog_has_exactly_100_valid_specs():
    specs = load_all_specs()
    assert len(specs) == 100

    by_category: dict[str, int] = {}
    for s in specs:
        by_category[s.category] = by_category.get(s.category, 0) + 1

    assert set(by_category.keys()) == VALID_CATEGORIES
    assert sum(by_category.values()) == 100


def test_full_catalog_ids_are_unique():
    specs = load_all_specs()
    ids = [s.id for s in specs]
    assert len(ids) == len(set(ids))
