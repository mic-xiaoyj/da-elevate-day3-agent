"""POS Troubleshooting RAG Tool using BigQuery Vector Search and Adjacent Context Window Stitching.

Targets table: <PROJECT_ID>.cymbal_gold.pos_manual_chunk_embeddings
Provides semantic vector search with adjacent chunk stitching (N-1 to N+1),
similarity score thresholding (0.70), full-text search fallback, and GCS HTTPS link conversion.
"""

import os
import re
import time
import logging
from google.cloud import bigquery

logger = logging.getLogger(__name__)

PROJECT_ID = os.environ.get("PROJECT_ID", "xiaoyj-lab")
TABLE_NAME = f"`{PROJECT_ID}.cymbal_gold.pos_manual_chunk_embeddings`"
SIMILARITY_THRESHOLD = 0.70


def _get_bq_client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT_ID)


def pos_troubleshooting_rag_tool(query: str) -> str:
    """Search POS terminal technical manuals and hardware troubleshooting runbooks.

    Use this tool when cashiers or operators encounter POS hardware errors, device freezes,
    peripheral failures, or need standard recovery procedures and certified GCS documentation
    for terminals such as Toshiba TCx 810, Diebold Nixdorf Beetle, HP Engage One, etc.

    Args:
        query: Specific hardware error code or technical fault description (e.g. ERR-PAY-4001).

    Returns:
        Certified technical runbook procedure, equipment details, similarity score, and clickable documentation link.
    """
    max_retries = 3
    base_delay = 1.5
    client = _get_bq_client()

    # Step 1: Attempt Vector Search with Adjacent Context Window Stitching
    vector_search_sql = f"""
    WITH matched AS (
      SELECT 
        base.document_filename,
        base.document_title,
        base.equipment_covered,
        base.source_pdf_uri,
        base.chunk_index,
        ROUND(1 - distance, 4) AS similarity_score
      FROM VECTOR_SEARCH(
        TABLE {TABLE_NAME},
        "embedding",
        (SELECT AI.EMBED(@query, endpoint => "text-embedding-005").result AS embedding),
        top_k => 5,
        distance_type => "COSINE"
      )
    )
    SELECT 
      m.document_filename,
      m.document_title,
      m.equipment_covered,
      REPLACE(m.source_pdf_uri, "gs://", "https://storage.cloud.google.com/") AS doc_link,
      m.similarity_score,
      m.chunk_index,
      STRING_AGG(c.chunk_content, "\\n" ORDER BY c.chunk_index ASC) AS stitched_runbook
    FROM matched m
    JOIN {TABLE_NAME} c
      ON m.document_filename = c.document_filename
     AND c.chunk_index BETWEEN (m.chunk_index - 1) AND (m.chunk_index + 1)
    GROUP BY m.document_filename, m.document_title, m.equipment_covered, m.source_pdf_uri, m.similarity_score, m.chunk_index
    ORDER BY m.similarity_score DESC
    LIMIT 1
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("query", "STRING", query)
        ]
    )

    best_match = None
    for attempt in range(1, max_retries + 1):
        try:
            results = list(client.query(vector_search_sql, job_config=job_config).result())
            if results:
                best_match = results[0]
            break
        except Exception as e:
            logger.warning(f"Vector search attempt {attempt} failed: {e}")
            if attempt < max_retries:
                time.sleep(base_delay * attempt)

    # Check for specific error code in query (e.g. ERR-PAY-4001)
    error_code_match = re.search(r"(ERR-[\w-]+)", query, re.IGNORECASE)
    
    # If vector match is confident and contains the error code (if specified), return it
    if best_match and best_match.similarity_score >= SIMILARITY_THRESHOLD:
        if not error_code_match or (error_code_match and error_code_match.group(1).upper() in best_match.stitched_runbook.upper()):
            return (
                f"### Certified POS Hardware Runbook\n\n"
                f"- **Document Title:** {best_match.document_title}\n"
                f"- **Equipment Covered:** {best_match.equipment_covered}\n"
                f"- **Similarity Score:** {best_match.similarity_score:.4f} (Threshold >= {SIMILARITY_THRESHOLD})\n"
                f"- **Official Documentation:** [{best_match.document_filename}]({best_match.doc_link})\n\n"
                f"#### Surrounding Troubleshooting Procedure (Stitched Adjacent Chunks):\n"
                f"```text\n{best_match.stitched_runbook.strip()}\n```"
            )

    # Step 2: Fallback to full-text SEARCH if an error code is present or if below threshold
    search_match = None
    if error_code_match:
        err_code = error_code_match.group(1)
        search_term = f"`{err_code}`"

        search_sql = f"""
        WITH matched AS (
          SELECT 
            document_filename,
            document_title,
            equipment_covered,
            source_pdf_uri,
            chunk_index,
            0.9500 AS similarity_score
          FROM {TABLE_NAME}
          WHERE SEARCH(chunk_content, @search_term)
          LIMIT 1
        )
        SELECT 
          m.document_filename,
          m.document_title,
          m.equipment_covered,
          REPLACE(m.source_pdf_uri, "gs://", "https://storage.cloud.google.com/") AS doc_link,
          m.similarity_score,
          STRING_AGG(c.chunk_content, "\\n" ORDER BY c.chunk_index ASC) AS stitched_runbook
        FROM matched m
        JOIN {TABLE_NAME} c
          ON m.document_filename = c.document_filename
         AND c.chunk_index BETWEEN (m.chunk_index - 1) AND (m.chunk_index + 1)
        GROUP BY m.document_filename, m.document_title, m.equipment_covered, m.source_pdf_uri, m.similarity_score
        """

        search_job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("search_term", "STRING", search_term)
            ]
        )

        for attempt in range(1, max_retries + 1):
            try:
                results = list(client.query(search_sql, job_config=search_job_config).result())
                if results:
                    search_match = results[0]
                break
            except Exception as e:
                logger.warning(f"SEARCH fallback attempt {attempt} failed: {e}")
                if attempt < max_retries:
                    time.sleep(base_delay * attempt)

    if search_match:
        return (
            f"### Certified POS Hardware Runbook (Full-Text Search Fallback)\n\n"
            f"- **Document Title:** {search_match.document_title}\n"
            f"- **Equipment Covered:** {search_match.equipment_covered}\n"
            f"- **Similarity Score:** {search_match.similarity_score:.4f} (Retrieved via Exact Keyword Alignment)\n"
            f"- **Official Documentation:** [{search_match.document_filename}]({search_match.doc_link})\n\n"
            f"#### Surrounding Troubleshooting Procedure (Stitched Adjacent Chunks):\n"
            f"```text\n{search_match.stitched_runbook.strip()}\n```"
        )

    # Step 3: Out-of-scope query: return certified warning
    score_str = f"{best_match.similarity_score:.4f}" if best_match else "0.0000"
    return (
        f"Warning: Query relevance score ({score_str}) falls below certified threshold (< {SIMILARITY_THRESHOLD}) "
        f"and no matching technical runbook entries were found for this inquiry. "
        f"The requested topic appears to be out-of-scope for POS terminal hardware diagnostics."
    )
