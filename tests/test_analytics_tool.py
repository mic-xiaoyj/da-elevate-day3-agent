"""Unit tests for cymbal_analytics_tool and Mandatory Partition Clarification Guardrail."""

import pytest
from unittest.mock import patch, MagicMock
from app.tools.analytics_tool import (
    cymbal_analytics_tool,
    check_partition_guardrail,
)


def test_partition_guardrail_triggers_on_unbounded_query():
    """Unbounded queries targeting partitioned ledgers must trigger the guardrail."""
    query = "Show all transactions from pos_transactions_gold"
    result = check_partition_guardrail(query)
    assert result is not None
    assert "Mandatory Partition Clarification Guardrail" in result
    assert "pos_transactions_gold" in result


def test_partition_guardrail_triggers_on_unbounded_alert_query():
    """Unbounded queries targeting pos_anomaly_alerts must trigger the guardrail."""
    query = "List all anomaly alerts in the system"
    result = check_partition_guardrail(query)
    assert result is not None
    assert "Mandatory Partition Clarification Guardrail" in result


def test_partition_guardrail_passes_bounded_query():
    """Queries with explicit temporal or entity bounds must pass through the guardrail."""
    bounded_queries = [
        "What is the total sales in pos_transactions_gold today?",
        "Show transactions from pos_transactions_gold for the last 7 days",
        "Check transactions for TXN-20260312-0015811",
        "Show cashiers with active cashier promo abuse alerts in the last 7 days",
        "What is Cashier CASH_1190's 7-day historical manual override baseline rate?",
    ]
    for q in bounded_queries:
        assert check_partition_guardrail(q) is None, f"Failed for query: {q}"


@patch("app.tools.analytics_tool.ask_data_agent")
@patch("app.tools.analytics_tool.google.auth.default")
def test_analytics_tool_success_with_mock_ask_data_agent(mock_auth, mock_ask):
    """Test cymbal_analytics_tool correctly formats native ask_data_agent responses."""
    mock_auth.return_value = (MagicMock(), "test-project")
    mock_ask.return_value = {
        "status": "SUCCESS",
        "response": [
            {
                "data": {
                    "generatedSql": "SELECT COUNT(*) FROM `cymbal_gold.pos_anomaly_alerts` WHERE alert_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)"
                }
            },
            {
                "Data Retrieved": {
                    "headers": ["total_alerts"],
                    "rows": [[42]],
                    "summary": "1 row returned"
                }
            },
            {
                "text": {
                    "textType": "FINAL_RESPONSE",
                    "parts": ["There were 42 anomaly alerts in the last 7 days."]
                }
            }
        ]
    }

    res = cymbal_analytics_tool("Show alert count for the last 7 days")
    assert "There were 42 anomaly alerts in the last 7 days." in res
    assert "SELECT COUNT(*)" in res
    assert "total_alerts" in res


@patch("app.tools.analytics_tool.ask_data_agent")
@patch("app.tools.analytics_tool.google.auth.default")
def test_analytics_tool_retry_and_fallback_on_failure(mock_auth, mock_ask):
    """Test cymbal_analytics_tool returns clean fallback error on persistent failure."""
    mock_auth.return_value = (MagicMock(), "test-project")
    mock_ask.return_value = {
        "status": "ERROR",
        "error_details": "Simulated connection refused"
    }

    res = cymbal_analytics_tool("Show inventory cover hours today")
    assert "Store data service is currently unreachable" in res
    assert "Simulated connection refused" in res
