"""Cloud Bigtable MCP Toolset & Real-Time Alert Reader.

Connects to the Cloud Run microservice hosting the MCP Database Toolbox:
mcp-toolbox-bigtable (Instance: operations-db, Tables: cashier_realtime_alerts, pos_transactions_enriched)
"""

import os
import json
import base64
import struct
import logging
import requests
from google.auth.transport.requests import Request
from google.oauth2 import id_token

from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

logger = logging.getLogger(__name__)


def _get_mcp_url() -> str:
    """Retrieve Cloud Run MCP service URL from environment without hardcoded sandbox fallbacks."""
    url = os.environ.get("BIGTABLE_MCP_URL")
    if not url:
        raise ValueError("BIGTABLE_MCP_URL environment variable must be set.")
    return url.rstrip("/")


def _get_id_token() -> str:
    """Fetch OIDC ID token for authenticating with Cloud Run MCP service."""
    auth_req = Request()
    return id_token.fetch_id_token(auth_req, _get_mcp_url())


def _get_auth_headers(context=None) -> dict[str, str]:
    try:
        return {"Authorization": f"Bearer {_get_id_token()}"}
    except Exception as e:
        logger.warning(f"Could not acquire OIDC token for MCP: {e}")
        return {}


# Initialize ADK McpToolset bound to Cloud Run MCP service
def get_bigtable_mcp_toolset() -> McpToolset:
    url = _get_mcp_url()
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=f"{url}/mcp",
            headers=_get_auth_headers()
        ),
        header_provider=_get_auth_headers
    )


# Lazy-loaded / module-level toolset
bigtable_mcp_toolset = None
try:
    if os.environ.get("BIGTABLE_MCP_URL"):
        bigtable_mcp_toolset = get_bigtable_mcp_toolset()
except Exception as _e:
    logger.warning(f"Could not initialize bigtable_mcp_toolset on module import: {_e}")


def decode_bigtable_event(raw_row: dict) -> dict:
    """Decodes base64-encoded Bigtable row columns and typed metrics."""
    row_key = raw_row.get("row_key", "")
    decoded = {"row_key": row_key, "flags": {}, "stats": {}}

    for k, v in raw_row.get("flags", {}).items():
        try:
            col = base64.b64decode(k).decode("utf-8", errors="ignore")
            val = base64.b64decode(v).decode("utf-8", errors="ignore")
            decoded["flags"][col] = val
        except Exception:
            decoded["flags"][k] = v

    for k, v in raw_row.get("stats", {}).items():
        try:
            col = base64.b64decode(k).decode("utf-8", errors="ignore")
            raw_bytes = base64.b64decode(v)
            if len(raw_bytes) == 8:
                if col.endswith("_count") or col.endswith("_txn"):
                    val = struct.unpack(">q", raw_bytes)[0]
                else:
                    val = round(struct.unpack(">d", raw_bytes)[0], 4)
            else:
                val = raw_bytes.decode("utf-8", errors="ignore")
            decoded["stats"][col] = val
        except Exception:
            decoded["stats"][k] = v

    # Calculate live manual override rate
    txns = decoded["stats"].get("cashier_1h_txn_count", 0)
    overrides = decoded["stats"].get("cashier_1h_manual_override_count", 0)
    if txns > 0:
        rate = round(overrides / txns, 4)
        decoded["stats"]["cashier_1h_override_rate"] = rate
        decoded["stats"]["cashier_1h_override_rate_pct"] = f"{rate * 100:.2f}%"

    return decoded


def read_cashier_realtime_alerts(store_id: str, cashier_id: str) -> str:
    """Query live 1-hour rolling metrics and audit status flags for a cashier in Cloud Bigtable.

    Use this tool when needing real-time operational status for a cashier (e.g. Cashier CASH_1190 at Store 48),
    such as live audit_status flag ('review' vs 'clear'), 1-hour manual override count, 1-hour transaction count,
    live override rate percentage, promo rate, total discount USD, or risk score.

    Args:
        store_id: Store number or ID (e.g. '48', '048', or 'STORE_048').
        cashier_id: Cashier number or ID (e.g. '1190', 'CASH_1190').

    Returns:
        Structured summary of live 1-hour cashier metrics and audit flags from Bigtable operations-db.
    """
    cleaned_store = str(store_id).strip().upper()
    if not cleaned_store.startswith("STORE_"):
        if cleaned_store.isdigit():
            cleaned_store = f"STORE_{int(cleaned_store):03d}"
        else:
            cleaned_store = f"STORE_{cleaned_store}"

    cleaned_cashier = str(cashier_id).strip().upper()
    if not cleaned_cashier.startswith("CASH_"):
        cleaned_cashier = f"CASH_{cleaned_cashier}"

    prefix = f"{cleaned_store}#{cleaned_cashier}%"

    try:
        url = _get_mcp_url()
        token = _get_id_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "query_cashier_realtime_alerts",
                "arguments": {
                    "row_key_prefix": prefix
                }
            }
        }
        resp = requests.post(f"{url}/mcp", headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("result", {})
            content = result.get("content", [])
            raw_rows = []
            for c in content:
                if isinstance(c, dict) and "text" in c:
                    try:
                        item = json.loads(c["text"])
                        if isinstance(item, list):
                            raw_rows.extend(item)
                        elif isinstance(item, dict):
                            raw_rows.append(item)
                    except Exception:
                        pass

            if not raw_rows:
                return f"No real-time alert events found in Bigtable for prefix '{prefix}'."

            latest = decode_bigtable_event(raw_rows[0])
            stats = latest["stats"]
            flags = latest["flags"]

            return (
                f"### Cloud Bigtable Real-Time Alert Event\n"
                f"- **Store:** {cleaned_store}\n"
                f"- **Cashier ID:** {cleaned_cashier}\n"
                f"- **Row Key:** `{latest['row_key']}`\n"
                f"- **Audit Status:** `{flags.get('audit_status', 'UNKNOWN')}`\n"
                f"- **Risk Score:** `{stats.get('risk_score', 0.0)}`\n"
                f"- **1-Hour Transaction Count:** {stats.get('cashier_1h_txn_count', 0)}\n"
                f"- **1-Hour Manual Override Count:** {stats.get('cashier_1h_manual_override_count', 0)}\n"
                f"- **1-Hour Manual Override Rate:** {stats.get('cashier_1h_override_rate_pct', '0.00%')}\n"
                f"- **1-Hour Promo Rate:** {stats.get('cashier_1h_promo_rate', 0.0) * 100:.2f}%\n"
                f"- **1-Hour Total Discount (USD):** ${stats.get('cashier_1h_total_discount_usd', 0.0):,.2f}\n"
            )
    except Exception as e:
        logger.error(f"Error calling Bigtable MCP tool: {e}")

    return f"Unable to retrieve real-time alerts from Cloud Bigtable for prefix '{prefix}'."


def read_pos_transactions_enriched(store_id: str, transaction_id: str) -> str:
    """Query enriched real-time POS transaction details and anomaly alert flags from Cloud Bigtable.

    Use this tool when looking up real-time transaction facts and alert annotations
    for a specific transaction at a store (e.g. Store 5, Transaction TXN-20260312-0015811).

    Args:
        store_id: Store identifier or number (e.g. '5', '005', 'STORE_005').
        transaction_id: Transaction ID (e.g. 'TXN-20260312-0015811').

    Returns:
        Structured JSON or summary of the transaction line items and anomaly alert flags.
    """
    cleaned_store = str(store_id).strip().upper()
    if not cleaned_store.startswith("STORE_"):
        if cleaned_store.isdigit():
            cleaned_store = f"STORE_{int(cleaned_store):03d}"
        else:
            cleaned_store = f"STORE_{cleaned_store}"

    cleaned_txn = str(transaction_id).strip().upper()
    row_key = f"{cleaned_store}#{cleaned_txn}"

    try:
        url = _get_mcp_url()
        token = _get_id_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "read_pos_transactions_enriched_sql",
                "arguments": {
                    "row_key": row_key
                }
            }
        }
        resp = requests.post(f"{url}/mcp", headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("result", {})
            content = result.get("content", [])
            raw_rows = []
            for c in content:
                if isinstance(c, dict) and "text" in c:
                    try:
                        item = json.loads(c["text"])
                        if isinstance(item, list):
                            raw_rows.extend(item)
                        elif isinstance(item, dict):
                            raw_rows.append(item)
                    except Exception:
                        pass
            if not raw_rows:
                return f"No enriched transaction record found in Bigtable for row key '{row_key}'."
            return f"### Enriched POS Transaction Record\n- **Row Key:** `{row_key}`\n```json\n{json.dumps(raw_rows[0], indent=2)}\n```"
    except Exception as e:
        logger.error(f"Error querying read_pos_transactions_enriched: {e}")

    return f"Unable to retrieve enriched transaction from Cloud Bigtable for row key '{row_key}'."
