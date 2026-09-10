"""Unit tests for root coordinator cymbal_operations_agent."""

import pytest
from app.agent import root_agent, COORDINATOR_INSTRUCTIONS


def test_agent_initialization():
    """Verify agent identity, description, and model configuration."""
    assert root_agent.name == "cymbal_operations_agent"
    assert "Root operational coordinator agent" in root_agent.description
    assert root_agent.model is not None


def test_agent_tools_registration():
    """Verify that all core operational tools are registered to the agent."""
    tool_names = [t.name if hasattr(t, "name") else str(t) for t in root_agent.tools]
    assert any("cymbal_analytics_tool" in name for name in tool_names)
    assert any("pos_troubleshooting_rag_tool" in name for name in tool_names)
    assert any("read_cashier_realtime_alerts" in name for name in tool_names)
    assert any("read_pos_transactions_enriched" in name for name in tool_names)


def test_coordinator_instructions_contain_guardrails():
    """Verify that system instructions enforce all required routing protocols and guardrails."""
    # Mandatory Partition Clarification Guardrail
    assert "Mandatory Partition Clarification Guardrail" in COORDINATOR_INSTRUCTIONS
    assert "pos_transactions_gold" in COORDINATOR_INSTRUCTIONS
    assert "pos_anomaly_alerts" in COORDINATOR_INSTRUCTIONS

    # Multi-tool Orchestration Protocols
    assert "Single-Tool Direct Dispatch" in COORDINATOR_INSTRUCTIONS
    assert "Parallel Tool Dispatch" in COORDINATOR_INSTRUCTIONS
    assert "Sequential Multi-Turn Dispatch" in COORDINATOR_INSTRUCTIONS
    assert "Estimated Cover Hours" in COORDINATOR_INSTRUCTIONS
