"""Unit tests for pos_troubleshooting_rag_tool, SQL error boosting, and SDD decline text."""

import pytest
from unittest.mock import patch, MagicMock
from app.tools.rag_tool import (
    pos_troubleshooting_rag_tool,
    _extract_error_code,
    _clean_keywords_for_search,
    MANDATED_DECLINE_TEXT,
)


def test_extract_error_code():
    """Verify hardware error codes are accurately extracted from natural queries."""
    assert _extract_error_code("How to fix ERR-PAY-4001 on terminal?") == "ERR-PAY-4001"
    assert _extract_error_code("Check ERR-DN-PRNT-24V cutter lock") == "ERR-DN-PRNT-24V"
    assert _extract_error_code("General thermal printer issue without code") == ""


def test_clean_keywords_for_search():
    """Verify keyword cleaning strips stopwords and handles error tokens."""
    cleaned_err = _clean_keywords_for_search("What is ERR-PAY-4001 protocol?")
    assert cleaned_err == "`ERR-PAY-4001`"

    cleaned_desc = _clean_keywords_for_search("How do we fix touchscreen freeze on Toshiba?")
    assert "touchscreen" in cleaned_desc
    assert "freeze" in cleaned_desc
    assert "Toshiba" in cleaned_desc
    assert "how" not in cleaned_desc


@patch("app.tools.rag_tool._get_bq_client")
def test_rag_tool_high_confidence_vector_match(mock_get_client):
    """Test confident vector match returns structured diagnostic procedure."""
    mock_row = MagicMock()
    mock_row.document_filename = "Toshiba_TCx_810_Guide.pdf"
    mock_row.document_title = "Toshiba TCx 810 Service Guide"
    mock_row.equipment_covered = "Toshiba TCx 810"
    mock_row.doc_link = "https://storage.cloud.google.com/bucket/Toshiba_TCx_810_Guide.pdf"
    mock_row.similarity_score = 0.9900  # Boosted error score
    mock_row.stitched_runbook = "Step 1: Do not re-swipe card. Step 2: Warm boot PIN Pad."

    mock_client = MagicMock()
    mock_client.query.return_value.result.return_value = [mock_row]
    mock_get_client.return_value = mock_client

    result = pos_troubleshooting_rag_tool("ERR-PAY-4001 EMV contactless payment freeze")
    assert "Certified POS Hardware Runbook" in result
    assert "Toshiba TCx 810" in result
    assert "0.9900" in result
    assert "Step 1: Do not re-swipe card" in result


@patch("app.tools.rag_tool._get_bq_client")
def test_rag_tool_out_of_bounds_exact_decline_string(mock_get_client):
    """Test out-of-scope inquiry returns the exact SDD-mandated decline warning."""
    mock_client = MagicMock()
    # Vector search returns empty or score < 0.70
    mock_client.query.return_value.result.return_value = []
    mock_get_client.return_value = mock_client

    result = pos_troubleshooting_rag_tool("How do I replace the engine oil on a Ford F-150 truck?")
    assert result == MANDATED_DECLINE_TEXT
    assert result == "I cannot find certified warranty or repair rules for this specific error in our technical repository."
