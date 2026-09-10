"""Tool wrapper for BigQuery Conversational Analytics Data Agent.

Interacts with the published BigQuery Conversational Data Agent for Cymbal Retail:
projects/xiaoyj-lab/locations/global/dataAgents/cymbal-retail-analytics
"""

import os
import json
import time
import logging
import requests
import google.auth
import google.auth.transport.requests

logger = logging.getLogger(__name__)

PROJECT_ID = os.environ.get("PROJECT_ID", "xiaoyj-lab")
LOCATION = os.environ.get("LOCATION", "global")
DATA_AGENT_NAME = os.environ.get(
    "DATA_AGENT_NAME",
    f"projects/{PROJECT_ID}/locations/{LOCATION}/dataAgents/cymbal-retail-analytics"
)

CHAT_URL = f"https://geminidataanalytics.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}:chat"


def _get_access_token() -> str:
    """Retrieve OAuth access token for Google Cloud APIs."""
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token


def cymbal_analytics_tool(query: str) -> str:
    """Execute analytical and conversational SQL queries against Cymbal Retail BigQuery gold tables.

    Use this tool for:
    - Daily store inventory reconciliation and stockout burn-rate analysis (gold_inventory_reconciliation_ledger)
    - Real-time intraday POS checkout ledger and transaction lookups (pos_transactions_gold)
    - Cashier promo abuse alerts and anomaly rankings (pos_anomaly_alerts)
    - Warranty policy terms and past purchase verification (warranty_generic_sections_extracted)
    - Historical customer transactions and 7-day cashier baseline metrics (historical_transactional_data)
    - Cross-cloud federated AWS S3 transactions (silver_pos_transactions via BigLake)

    Args:
        query: Verbatim natural language inquiry referencing enterprise business terms.

    Returns:
        Formatted analytical response including generated SQL and data summary.
    """
    max_retries = 3
    base_delay = 2.0

    payload = {
        "dataAgentContext": {
            "dataAgent": DATA_AGENT_NAME
        },
        "messages": [
            {
                "userMessage": {
                    "text": query
                }
            }
        ]
    }

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            token = _get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            response = requests.post(CHAT_URL, headers=headers, json=payload, timeout=60)
            if response.status_code == 200:
                events = response.json()
                if not isinstance(events, list):
                    return str(events)

                final_answer_parts = []
                generated_sql = None
                result_data = None

                for event in events:
                    sys_msg = event.get("systemMessage", {})
                    
                    # Thought or final text
                    text_obj = sys_msg.get("text", {})
                    text_type = text_obj.get("textType")
                    parts = text_obj.get("parts", [])
                    if text_type == "FINAL_RESPONSE":
                        final_answer_parts.extend(parts)

                    # SQL query
                    data_obj = sys_msg.get("data", {})
                    matched_query = data_obj.get("matchedQuery", {}).get("exampleQuery", {})
                    if "sqlQuery" in matched_query:
                        generated_sql = matched_query["sqlQuery"]
                    
                    # Query data results
                    if "result" in data_obj and "data" in data_obj["result"]:
                        result_data = data_obj["result"]["data"]

                output_lines = []
                if final_answer_parts:
                    output_lines.append("\n".join(final_answer_parts))
                if generated_sql:
                    output_lines.append(f"\n```sql\n{generated_sql.strip()}\n```")
                if result_data:
                    output_lines.append(f"\nRetrieved Data ({len(result_data)} rows):")
                    output_lines.append(json.dumps(result_data[:10], indent=2))

                if output_lines:
                    return "\n".join(output_lines)
                else:
                    return "Query processed successfully, but no response payload returned."

            else:
                last_error = f"HTTP {response.status_code}: {response.text}"
                logger.warning(f"Data agent request failed (attempt {attempt}/{max_retries}): {last_error}")

        except Exception as e:
            last_error = str(e)
            logger.warning(f"Transient error querying data agent (attempt {attempt}/{max_retries}): {e}")

        if attempt < max_retries:
            time.sleep(base_delay * (2 ** (attempt - 1)))

    return f"Store data service is currently unreachable due to database connectivity failure. Details: {last_error}"
