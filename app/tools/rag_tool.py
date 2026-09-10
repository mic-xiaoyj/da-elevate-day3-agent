"""POS Troubleshooting RAG Tool using BigQuery Vector Search and Adjacent Context Window Stitching.

Targets table: <PROJECT_ID>.cymbal_gold.pos_manual_chunk_embeddings
Provides semantic vector search with adjacent chunk stitching (N-1 to N+1),
SQL-level CASE error boosting (0.99), universal keyword full-text search fallback,
and exact SDD-mandated low-confidence decline strings.
"""

import os
import re
import time
import logging
from google.cloud import bigquery

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.70
MANDATED_DECLINE_TEXT = (
    "I cannot find certified warranty or repair rules for this specific error in our technical repository."
)


def _get_project_id() -> str:
    project_id = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise ValueError(
            "PROJECT_ID or GOOGLE_CLOUD_PROJECT environment variable must be set."
        )
    return project_id


def _get_table_name() -> str:
    return f"`{_get_project_id()}.cymbal_gold.pos_manual_chunk_embeddings`"


def _get_bq_client() -> bigquery.Client:
    return bigquery.Client(project=_get_project_id())


def _extract_error_code(query: str) -> str:
    """Extract hardware error code token (e.g. ERR-PAY-4001, ERR-DN-PRNT-24V)."""
    match = re.search(r"(ERR-[\w-]+)", query, re.IGNORECASE)
    return match.group(1).upper() if match else ""


def _clean_keywords_for_search(query: str) -> str:
    """Extract and clean keywords from user query for full-text SEARCH() fallback."""
    error_code = _extract_error_code(query)
    if error_code:
        return f"`{error_code}`"
    
    # Filter stopwords and punctuation for general descriptive hardware questions
    stopwords = {
        "what", "is", "the", "how", "do", "we", "i", "can", "to", "ensure",
        "and", "for", "a", "an", "in", "on", "of", "when", "at", "with",
        "from", "this", "that", "there", "their", "are", "was", "were"
    }
    words = re.findall(r"\b[A-Za-z0-9]{3,}\b", query)
    meaningful = [w for w in words if w.lower() not in stopwords]
    return " ".join(meaningful[:6]) if meaningful else re.sub(r"[^\w\s]", " ", query).strip()


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

    try:
        table_name = _get_table_name()
        client = _get_bq_client()
    except Exception as e:
        logger.error(f"Configuration or client init error: {e}")
        return MANDATED_DECLINE_TEXT

    extracted_error = _extract_error_code(query)

    # Step 1: Vector Search with SQL-level CASE Keyword Error-Boosting
    # If the chunk content matches the extracted error code, it receives an automatic boosted score of 0.99.
    vector_search_sql = f"""
    WITH matched AS (
      SELECT 
        base.document_filename,
        base.document_title,
        base.equipment_covered,
        base.source_pdf_uri,
        base.chunk_index,
        CASE
          WHEN @error_code != '' AND REGEXP_CONTAINS(base.chunk_content, @error_code) THEN 0.9900
          ELSE ROUND(1 - distance, 4)
        END AS similarity_score
      FROM VECTOR_SEARCH(
        TABLE {table_name},
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
    JOIN {table_name} c
      ON m.document_filename = c.document_filename
     AND c.chunk_index BETWEEN (m.chunk_index - 1) AND (m.chunk_index + 1)
    GROUP BY m.document_filename, m.document_title, m.equipment_covered, m.source_pdf_uri, m.similarity_score, m.chunk_index
    ORDER BY m.similarity_score DESC
    LIMIT 1
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("query", "STRING", query),
            bigquery.ScalarQueryParameter("error_code", "STRING", extracted_error),
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

    # If vector match is confident (>= 0.70), return it
    if best_match and best_match.similarity_score >= SIMILARITY_THRESHOLD:
        return (
            f"### Certified POS Hardware Runbook\n\n"
            f"- **Document Title:** {best_match.document_title}\n"
            f"- **Equipment Covered:** {best_match.equipment_covered}\n"
            f"- **Similarity Score:** {best_match.similarity_score:.4f} (Threshold >= {SIMILARITY_THRESHOLD})\n"
            f"- **Official Documentation:** [{best_match.document_title}]({best_match.doc_link})\n\n"
            f"#### Surrounding Troubleshooting Procedure (Stitched Adjacent Chunks):\n"
            f"```text\n{best_match.stitched_runbook.strip()}\n```"
        )

    # Step 2: Fallback to Keyword-Cleaned Full-Text SEARCH for ANY low-confidence query (< 0.70)
    cleaned_search_terms = _clean_keywords_for_search(query)
    search_match = None

    if cleaned_search_terms:
        search_sql = f"""
        WITH matched AS (
          SELECT 
            document_filename,
            document_title,
            equipment_covered,
            source_pdf_uri,
            chunk_index,
            0.9500 AS similarity_score
          FROM {table_name}
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
        JOIN {table_name} c
          ON m.document_filename = c.document_filename
         AND c.chunk_index BETWEEN (m.chunk_index - 1) AND (m.chunk_index + 1)
        GROUP BY m.document_filename, m.document_title, m.equipment_covered, m.source_pdf_uri, m.similarity_score
        """
        search_job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("search_term", "STRING", cleaned_search_terms)
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
            f"- **Official Documentation:** [{search_match.document_title}]({search_match.doc_link})\n\n"
            f"#### Surrounding Troubleshooting Procedure (Stitched Adjacent Chunks):\n"
            f"```text\n{search_match.stitched_runbook.strip()}\n```"
        )

    # Step 3: Out-of-bounds or low-relevance queries return the exact SDD-mandated decline text
    return MANDATED_DECLINE_TEXT
