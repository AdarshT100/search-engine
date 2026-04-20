# Route handlers for GET /api/search and GET /api/autocomplete endpoints.
"""
app/api/search.py

Public search and autocomplete endpoints.
No authentication required on either route.

Routes:
    GET /api/search?q=&page=&source=
    GET /api/autocomplete?prefix=
"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.data.db import get_db
from app.data.redis_client import get_redis
from app.services.search_service import SearchService

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api", tags=["search"])

# ---------------------------------------------------------------------------
# Error helper  (mirrors the pattern used in app/api/auth.py)
# ---------------------------------------------------------------------------


def _error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "status": status_code}},
    )


# ---------------------------------------------------------------------------
# Response / request models
# ---------------------------------------------------------------------------


class SearchResult(BaseModel):
    doc_id: str
    title: str
    snippet: str
    score: float
    source: str
    created_at: str


class SearchResponse(BaseModel):
    query: str
    page: int
    total_results: int
    total_pages: int
    results: list[SearchResult]


class AutocompleteResponse(BaseModel):
    prefix: str
    suggestions: list[str]


# ---------------------------------------------------------------------------
# GET /api/search
# ---------------------------------------------------------------------------


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Search indexed documents",
    description=(
        "Full-text search over all indexed documents using TF-IDF cosine similarity. "
        "Returns ranked, paginated results. No authentication required."
    ),
)
def search(
    q: str = Query(
        ...,
        description="Search query. Min 2 chars, max 200 chars.",
    ),
    page: int = Query(
        default=1,
        ge=1,
        description="Page number (1-based). Returns 10 results per page.",
    ),
    source: Optional[str] = Query(
        default=None,
        description="Filter by document source. Values: 'static' or 'uploaded'.",
    ),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """
    Search Flow (SDD §4.1):
      1. Validate query length.
      2. Optionally validate source filter value.
      3. Delegate to SearchService — preprocessing, index lookup,
         TF-IDF re-scoring, snippet generation, pagination.
      4. Return structured JSON matching API Contract §2.
    """
    # ── Validation: query length ───────────────────────────────────────────
    if len(q) < 2:
        raise _error(
            "QUERY_TOO_SHORT",
            "Query must be at least 2 characters.",
            400,
        )

    if len(q) > 200:
        raise _error(
            "QUERY_TOO_LONG",
            "Query must be under 200 characters.",
            400,
        )

    # ── Validation: source filter ──────────────────────────────────────────
    # Reject unknown values early so SearchService never receives bad input.
    VALID_SOURCES = {"static", "uploaded"}
    if source is not None and source not in VALID_SOURCES:
        raise _error(
            "INVALID_SOURCE_FILTER",
            "source must be 'static' or 'uploaded'.",
            400,
        )

    # ── Delegate to SearchService ──────────────────────────────────────────
    result: dict = SearchService(db).search(
        query=q,
        page=page,
        source_filter=source,
    )

    # SearchService guarantees the correct dict shape even for 0 results.
    return SearchResponse(**result)


# ---------------------------------------------------------------------------
# GET /api/autocomplete
# ---------------------------------------------------------------------------


@router.get(
    "/autocomplete",
    response_model=AutocompleteResponse,
    summary="Get autocomplete suggestions",
    description=(
        "Returns up to 5 term suggestions based on a prefix. "
        "Powered by an in-memory prefix trie stored in Redis. "
        "Returns an empty list if the trie is not available — never crashes."
    ),
)
def autocomplete(
    prefix: str = Query(
        ...,
        min_length=1,
        description="The partial word typed by the user. Min 1 character.",
    ),
) -> AutocompleteResponse:
    """
    Autocomplete Flow:
      1. Fetch serialised prefix trie from Redis key 'autocomplete:trie'.
      2. If the key is missing or malformed, return empty suggestions silently.
      3. Walk the trie to collect all completions that start with *prefix*.
      4. Return the top 5 matches (alphabetical order is used as a stable tie-break).

    The trie stored in Redis is expected to be a JSON object where:
        { "term": true, ... }  — i.e. a flat dict of all indexed terms.

    If the trie is stored as a nested structure, replace _flat_trie_lookup
    with the appropriate traversal for that structure.
    """
    suggestions: list[str] = []

    try:
        redis = get_redis()
        raw = redis.get("autocomplete:trie")

        if raw is not None:
            trie: Any = json.loads(raw)
            suggestions = _flat_trie_lookup(trie, prefix)

    except Exception:
        # Redis unavailable, JSON malformed, unexpected trie shape, etc.
        # The spec is explicit: never crash — return empty list.
        suggestions = []

    return AutocompleteResponse(prefix=prefix, suggestions=suggestions)


# ---------------------------------------------------------------------------
# Trie lookup helper
# ---------------------------------------------------------------------------


def _flat_trie_lookup(trie: Any, prefix: str) -> list[str]:
    """
    Extract up to 5 completions from the trie that begin with *prefix*.

    Handles two storage shapes:
      - Flat dict  : { "machine": true, "machinist": true, ... }
      - Nested dict: { "m": { "a": { ... "$": true } } }  — traversed recursively

    In both cases the comparison is case-insensitive; returned terms preserve
    whatever case is stored in the trie (typically lowercase after NLP pipeline).

    Args:
        trie:   Deserialised trie object (dict or nested dict).
        prefix: Lowercased prefix string from the query parameter.

    Returns:
        A list of up to 5 matching terms, sorted alphabetically.
    """
    prefix_lower = prefix.lower()
    matches: list[str] = []

    if not isinstance(trie, dict):
        return matches

    # ── Flat dict shape: keys are complete terms ───────────────────────────
    # Heuristic: if any value is not a dict, treat the whole structure as flat.
    sample_values = list(trie.values())[:5]
    is_flat = any(not isinstance(v, dict) for v in sample_values)

    if is_flat:
        for term in trie:
            if isinstance(term, str) and term.lower().startswith(prefix_lower):
                matches.append(term)
                if len(matches) >= 5:
                    break
        return sorted(matches)[:5]

    # ── Nested trie shape: traverse character by character ─────────────────
    _collect_from_nested(trie, prefix_lower, "", matches)
    return sorted(matches)[:5]


def _collect_from_nested(
    node: dict,
    prefix: str,
    current: str,
    matches: list[str],
    max_results: int = 5,
) -> None:
    """
    Recursive DFS over a nested character trie.

    Conventions assumed:
      - Each key is a single character, except the sentinel key "$" which
        marks the end of a complete term.
      - Example: "cat" is stored as {"c": {"a": {"t": {"$": True}}}}

    Stops collecting once *max_results* terms have been found.
    """
    if len(matches) >= max_results:
        return

    # If we've consumed the full prefix, collect all reachable completions.
    if len(current) >= len(prefix):
        if "$" in node:
            matches.append(current)
        for char, child in node.items():
            if char != "$" and isinstance(child, dict) and len(matches) < max_results:
                _collect_from_nested(child, prefix, current + char, matches, max_results)
        return

    # Still navigating down to the prefix start.
    next_char = prefix[len(current)]
    if next_char in node and isinstance(node[next_char], dict):
        _collect_from_nested(
            node[next_char], prefix, current + next_char, matches, max_results
        )