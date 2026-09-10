"""Cloud Bigtable MCP Toolset & Real-Time Alert Reader.

Connects to the Cloud Run microservice hosting the MCP Database Toolbox:
mcp-toolbox-bigtable (Instance: operations-db, Table: cashier_realtime_alerts)
"""

import os
import json
import base64
import struct
import logging
import requests
import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import id_token

from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

logger = logging.getLogger(__name__)

BIGTABLE_MCP_URL = os.environ.get(
    "BIGTABLE_MCP_URL",
    "https://mcp-toolbox-bigtable-737446388661.us-central1.run.app"
)


def _get_id_token() -> str:
    """Fetch OIDC ID token for authenticating with Cloud Run MCP service."""
    auth_req = Request()
    return id_token.fetch_id_token(auth_req, BIGTABLE_MCP_URL)


def _get_auth_headers(context=None) -> dict[str, str]:
    return {"Authorization": f"Bearer {_get_id_token()}"}


# Initialize ADK McpToolset bound to Cloud Run MCP service
bigtable_mcp_toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=f"{BIGTABLE_MCP_URL}/mcp",
        headers={"Authorization": f"Bearer {_get_id_token()}"}
    ),
    header_provider=_get_auth_headers
)


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
    # Normalize IDs
    s_num = store_id.replace("STORE_", "").strip().zfill(3)
    c_num = cashier_id.replace("CASH_", "").strip()
    row_key_prefix = f"STORE_{s_num}#CASH_{c_num}%"

    token = _get_id_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "query_cashier_realtime_alerts",
            "arguments": {
                "row_key_prefix": row_key_prefix
            }
        }
    }

    try:
        resp = requests.post(f"{BIGTABLE_MCP_URL}/mcp", headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            return f"Error connecting to Bigtable MCP microservice: HTTP {resp.status_code} - {resp.text}"

        res_json = resp.json()
        result = res_json.get("result", {})
        if result.get("isError"):
            err_text = " ".join([c.get("text", "") for c in result.get("content", [])])
            return f"Bigtable MCP tool error: {err_text}"

        contents = result.get("content", [])
        if not contents:
            return f"No real-time alerts found in Bigtable for prefix '{row_key_prefix}'."

        decoded_rows = []
        for c in contents:
            raw_text = c.get("text", "{}")
            try:
                row_dict = json.loads(raw_text)
                decoded_rows.append(decode_bigtable_event(row_dict))
            except Exception:
                pass

        if not decoded_rows:
            return f"No valid alert rows could be parsed for {row_key_prefix}."

        latest = decoded_rows[0]
        stats = latest["stats"]
        flags = latest["flags"]

        summary = (
            f"### Cloud Bigtable Real-Time Alert Report\n\n"
            f"- **Target Row Key:** `{latest['row_key']}`\n"
            f"- **Store / Cashier:** Store {s_num} / Cashier CASH_{c_num}\n"
            f"- **Audit Status Flag:** `{flags.get('audit_status', 'UNKNOWN').upper()}`\n"
            f"- **Last Event Timestamp:** `{stats.get('last_event_ts', 'N/A')}`\n"
            f"- **Risk Score:** `{stats.get('risk_score', 0.0)}`\n\n"
            f"#### Live 1-Hour Rolling Metrics:\n"
            f"- **Live 1h Transaction Count:** {stats.get('cashier_1h_txn_count', 0)}\n"
            f"- **Live 1h Manual Override Count:** {stats.get('cashier_1h_manual_override_count', 0)}\n"
            f"- **Live 1h Manual Override Rate:** **{stats.get('cashier_1h_override_rate_pct', 'N/A')}**\n"
            f"- **Live 1h Promo Count:** {stats.get('cashier_1h_promo_count', 0)}\n"
            f"- **Live 1h Promo Rate:** {stats.get('cashier_1h_promo_rate', 0.0) * 100:.2f}%\n"
            f"- **Live 1h Average Discount:** {stats.get('cashier_1h_avg_discount_pct', 0.0):.2f}%\n"
            f"- **Live 1h Total Discount USD:** ${stats.get('cashier_1h_total_discount_usd', 0.0):,.2f}\n"
        )
        return summary

    except Exception as e:
        return f"Error executing Bigtable query via MCP microservice: {str(e)}"
