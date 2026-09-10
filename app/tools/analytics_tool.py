"""Tool wrapper for BigQuery Conversational Analytics Data Agent.

Interacts with the published BigQuery Conversational Data Agent using ADK's native
ask_data_agent tool library (google.adk.tools.data_agent.data_agent_tool.ask_data_agent).
"""

import os
import re
import json
import time
import logging
import google.auth
from google.adk.tools.data_agent.data_agent_tool import (
    ask_data_agent,
    DataAgentToolConfig,
)

logger = logging.getLogger(__name__)


def _get_project_id() -> str:
    """Retrieve target GCP project ID from environment without hardcoded sandbox fallbacks."""
    project_id = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise ValueError(
            "PROJECT_ID or GOOGLE_CLOUD_PROJECT environment variable must be set."
        )
    return project_id


def _get_data_agent_name() -> str:
    """Resolve the published BigQuery Conversational Data Agent resource name."""
    configured_name = os.environ.get("DATA_AGENT_NAME")
    if configured_name:
        return configured_name

    project_id = _get_project_id()
    location = os.environ.get("LOCATION", "global")
    agent_id = os.environ.get("DATA_AGENT_ID", "cymbal-retail-analytics")
    return f"projects/{project_id}/locations/{location}/dataAgents/{agent_id}"


def check_partition_guardrail(query: str) -> str | None:
    """Mandatory Partition Clarification Guardrail.

    Evaluates whether an unbounded query against partitioned tables (`pos_transactions_gold`,
    `pos_anomaly_alerts`) lacks a date range or partition constraint, and prompts for clarification
    to prevent costly full table scans.
    """
    lower_q = query.lower()
    targets_partitioned = any(
        tbl in lower_q
        for tbl in [
            "pos_transactions_gold",
            "pos_anomaly_alerts",
            "transaction ledger",
            "alert ledger",
            "all transactions",
            "all anomaly alerts",
        ]
    )
    has_temporal_bound = bool(
        re.search(
            r"\b(today|yesterday|current_date|current_timestamp|hours?|days?|weeks?|months?|years?|last|latest|recent|since|interval|txn-[\w-]+|cash_[\w-]+|store_[\w-]+|202\d)\b",
            lower_q,
        )
    )
    if targets_partitioned and not has_temporal_bound:
        return (
            "Mandatory Partition Clarification Guardrail: Queries against partitioned ledgers "
            "(`pos_transactions_gold`, `pos_anomaly_alerts`) require an explicit date or lookback window "
            "(e.g., 'today', 'last 7 days', or specific business_date) to prevent unbounded full table scans. "
            "Please clarify the specific time frame or partition you would like to analyze."
        )
    return None


def cymbal_analytics_tool(query: str) -> str:
    """Execute analytical and conversational SQL queries against Cymbal Retail BigQuery gold tables.

    Uses ADK native ask_data_agent with server-side parameter pinning, exponential backoff,
    and the Mandatory Partition Clarification Guardrail.

    Args:
        query: Verbatim natural language inquiry referencing enterprise business terms.

    Returns:
        Formatted analytical response including generated SQL and data summary.
    """
    # 1. Pre-execution Partition Clarification Guardrail Check
    guardrail_response = check_partition_guardrail(query)
    if guardrail_response:
        return guardrail_response

    # 2. Parameter Pinning & Native Credentials
    try:
        data_agent_name = _get_data_agent_name()
    except Exception as e:
        return f"Configuration Error: {e}"

    location = os.environ.get("LOCATION", "global")
    settings = DataAgentToolConfig(location=location)

    try:
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
    except Exception as e:
        return f"Authentication Error: Unable to acquire default credentials: {e}"

    max_retries = 3
    base_delay = 2.0
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            res = ask_data_agent(
                data_agent_name=data_agent_name,
                query=query,
                credentials=credentials,
                settings=settings,
                tool_context=None,
            )

            if res.get("status") == "SUCCESS":
                response_steps = res.get("response", [])
                final_answer_parts = []
                thought_parts = []
                generated_sql = None
                retrieved_data = None

                for step in response_steps:
                    if not isinstance(step, dict):
                        continue

                    # Text extraction
                    text_obj = step.get("text", {})
                    text_type = text_obj.get("textType")
                    parts = text_obj.get("parts", [])
                    if text_type == "FINAL_RESPONSE":
                        final_answer_parts.extend(parts)
                    elif text_type == "THOUGHT":
                        thought_parts.extend(parts)
                    elif parts and not final_answer_parts:
                        thought_parts.extend(parts)

                    # SQL extraction
                    data_obj = step.get("data", {})
                    if "generatedSql" in data_obj:
                        generated_sql = data_obj["generatedSql"]
                    elif "matchedQuery" in data_obj:
                        matched = data_obj["matchedQuery"].get("exampleQuery", {})
                        if "sqlQuery" in matched:
                            generated_sql = matched["sqlQuery"]

                    # Data extraction
                    if "Data Retrieved" in step:
                        retrieved_data = step["Data Retrieved"]

                output_lines = []
                if final_answer_parts:
                    output_lines.append("\n".join(final_answer_parts))
                elif thought_parts:
                    output_lines.append("\n".join(thought_parts))
                if generated_sql:
                    output_lines.append(f"\n```sql\n{generated_sql.strip()}\n```")
                if retrieved_data:
                    summary = retrieved_data.get("summary", "")
                    headers = retrieved_data.get("headers", [])
                    rows = retrieved_data.get("rows", [])
                    output_lines.append(f"\nRetrieved Data ({summary}):")
                    if headers and rows:
                        output_lines.append(f"Columns: {', '.join(headers)}")
                        output_lines.append(json.dumps(rows[:10], indent=2))

                if output_lines:
                    return "\n".join(output_lines)
                return "Query processed successfully, but no response payload returned."
            else:
                last_error = res.get("error_details", "Unknown error from ask_data_agent")
                logger.warning(
                    f"ask_data_agent failed (attempt {attempt}/{max_retries}): {last_error}"
                )

        except Exception as e:
            last_error = str(e)
            logger.warning(
                f"Transient error calling ask_data_agent (attempt {attempt}/{max_retries}): {e}"
            )

        if attempt < max_retries:
            time.sleep(base_delay * (2 ** (attempt - 1)))

    return (
        f"Store data service is currently unreachable due to database connectivity failure. "
        f"Details: {last_error}"
    )
