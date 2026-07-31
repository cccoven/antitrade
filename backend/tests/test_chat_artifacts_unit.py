import json

from services.chat import _tool_artifact


def test_market_tool_output_becomes_versioned_artifact():
    artifact = _tool_artifact(
        "get_stock_market_data",
        "call-1",
        json.dumps({"symbol": "AAPL", "quote": {"price": 200}}),
    )

    assert artifact == {
        "id": "call-1",
        "type": "market_snapshot",
        "version": 1,
        "data": {"symbol": "AAPL", "quote": {"price": 200}},
    }


def test_unrelated_tool_output_is_not_an_artifact():
    assert _tool_artifact("get_journal_stats", "call-2", "{}") is None
