"""Unit tests for Cloud Bigtable MCP tools, metric decoding, and event parsing."""

import base64
import struct
import pytest
from unittest.mock import patch, MagicMock
from app.tools.bigtable_tool import (
    decode_bigtable_event,
    read_cashier_realtime_alerts,
    read_pos_transactions_enriched,
)


def test_decode_bigtable_event_binary_metrics():
    """Verify base64 binary decoding for typed Bigtable columns."""
    # Construct synthetic raw Bigtable row
    flag_audit = base64.b64encode(b"audit_status").decode("ascii")
    flag_val = base64.b64encode(b"REVIEW").decode("ascii")

    col_txns = base64.b64encode(b"cashier_1h_txn_count").decode("ascii")
    val_txns = base64.b64encode(struct.pack(">q", 52)).decode("ascii")

    col_overrides = base64.b64encode(b"cashier_1h_manual_override_count").decode("ascii")
    val_overrides = base64.b64encode(struct.pack(">q", 37)).decode("ascii")

    col_discount = base64.b64encode(b"cashier_1h_total_discount_usd").decode("ascii")
    val_discount = base64.b64encode(struct.pack(">d", 13123.78)).decode("ascii")

    col_risk = base64.b64encode(b"risk_score").decode("ascii")
    val_risk = base64.b64encode(struct.pack(">d", 1.0)).decode("ascii")

    raw_row = {
        "row_key": "STORE_048#CASH_1190#9221583025816952807",
        "flags": {flag_audit: flag_val},
        "stats": {
            col_txns: val_txns,
            col_overrides: val_overrides,
            col_discount: val_discount,
            col_risk: val_risk,
        }
    }

    decoded = decode_bigtable_event(raw_row)
    assert decoded["row_key"] == "STORE_048#CASH_1190#9221583025816952807"
    assert decoded["flags"]["audit_status"] == "REVIEW"
    assert decoded["stats"]["cashier_1h_txn_count"] == 52
    assert decoded["stats"]["cashier_1h_manual_override_count"] == 37
    assert decoded["stats"]["cashier_1h_total_discount_usd"] == 13123.78
    assert decoded["stats"]["risk_score"] == 1.0
    assert decoded["stats"]["cashier_1h_override_rate"] == 0.7115
    assert decoded["stats"]["cashier_1h_override_rate_pct"] == "71.15%"


@patch("app.tools.bigtable_tool._get_id_token", return_value="mock-token")
@patch("app.tools.bigtable_tool._get_mcp_url", return_value="https://mock-mcp-service.run.app")
@patch("app.tools.bigtable_tool.requests.post")
def test_read_cashier_realtime_alerts_mock(mock_post, mock_url, mock_token):
    """Test read_cashier_realtime_alerts formats MCP response correctly."""
    flag_audit = base64.b64encode(b"audit_status").decode("ascii")
    flag_val = base64.b64encode(b"REVIEW").decode("ascii")
    col_txns = base64.b64encode(b"cashier_1h_txn_count").decode("ascii")
    val_txns = base64.b64encode(struct.pack(">q", 10)).decode("ascii")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "result": {
            "content": [
                {
                    "text": f'[{{"row_key": "STORE_048#CASH_1190", "flags": {{"{flag_audit}": "{flag_val}"}}, "stats": {{"{col_txns}": "{val_txns}"}}}}]'
                }
            ]
        }
    }
    mock_post.return_value = mock_resp

    result = read_cashier_realtime_alerts("48", "1190")
    assert "Cloud Bigtable Real-Time Alert Event" in result
    assert "STORE_048" in result
    assert "CASH_1190" in result
    assert "REVIEW" in result


@patch("app.tools.bigtable_tool._get_id_token", return_value="mock-token")
@patch("app.tools.bigtable_tool._get_mcp_url", return_value="https://mock-mcp-service.run.app")
@patch("app.tools.bigtable_tool.requests.post")
def test_read_pos_transactions_enriched_mock(mock_post, mock_url, mock_token):
    """Test read_pos_transactions_enriched queries and formats transaction record."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "result": {
            "content": [
                {
                    "text": '[{"row_key": "STORE_005#TXN-001", "tx": {"total": 222.99}}]'
                }
            ]
        }
    }
    mock_post.return_value = mock_resp

    result = read_pos_transactions_enriched("STORE_005", "TXN-001")
    assert "Enriched POS Transaction Record" in result
    assert "STORE_005#TXN-001" in result
    assert "222.99" in result
