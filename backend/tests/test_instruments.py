import pytest

from services.instruments import FUTURES_SPECS, get_instrument_spec, position_risk_amount


@pytest.mark.parametrize(
    ("symbol", "point_value", "expected"),
    [
        ("NQ", 20.0, 400.0),
        ("MNQ", 2.0, 40.0),
        ("ES", 50.0, 1000.0),
        ("MES", 5.0, 100.0),
        ("GC", 100.0, 2000.0),
        ("MGC", 10.0, 200.0),
    ],
)
def test_futures_contract_risk_uses_point_value(symbol, point_value, expected):
    assert get_instrument_spec("futures", symbol)["point_value"] == point_value
    assert position_risk_amount("futures", symbol, 100, 90, 2) == expected


def test_unknown_or_forex_instrument_does_not_guess_risk():
    assert position_risk_amount("futures", "UNKNOWN", 100, 90, 1) is None
    assert position_risk_amount("forex", "EURUSD", 1.1, 1.09, 10000) is None


def test_calculation_specs_do_not_expose_provider_identifiers():
    for spec in FUTURES_SPECS.values():
        assert "provider_symbol" not in spec
        assert "exchange" not in spec
