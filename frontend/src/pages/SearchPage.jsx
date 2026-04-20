import { useState, useCallback } from "react";

const BASE_URL = import.meta.env.VITE_API_BASE_URL;

const RESULTS_PER_PAGE = 10;

/* ─── Small reusable pieces ──────────────────────────────────────────── */

function SourceBadge({ source }) {
  const isStatic = source === "static";
  return (
    <span style={{
      display: "inline-block",
      fontSize: "11px",
      fontWeight: 500,
      padding: "2px 8px",
      borderRadius: "999px",
      background: isStatic ? "#E6F1FB" : "#E1F5EE",
      color: isStatic ? "#0C447C" : "#085041",
      border: isStatic ? "0.5px solid #B5D4F4" : "0.5px solid #9FE1CB",
      letterSpacing: "0.02em",
    }}>
      {isStatic ? "Static" : "Uploaded"}
    </span>
  );
}

function Spinner() {
  return (
    <div style={{ display: "flex", justifyContent: "center", padding: "2.5rem 0" }}>
      <div style={{
        width: 28,
        height: 28,
        border: "2.5px solid var(--color-border-tertiary)",
        borderTopColor: "var(--color-text-secondary)",
        borderRadius: "50%",
        animation: "spin 0.7s linear infinite",
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function ResultCard({ result, showScore }) {
  return (
    <div style={{
      background: "var(--color-background-primary)",
      border: "0.5px solid var(--color-border-tertiary)",
      borderRadius: "var(--border-radius-lg)",
      padding: "1rem 1.25rem",
      display: "flex",
      flexDirection: "column",
      gap: 8,
    }}>
      {/* Header row: title + badge */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
        <h3 style={{
          margin: 0,
          fontSize: "15px",
          fontWeight: 500,
          color: "var(--color-text-primary)",
          lineHeight: 1.4,
        }}>
          {result.title}
        </h3>
        <SourceBadge source={result.source} />
      </div>

      {/* Snippet */}
      <p style={{
        margin: 0,
        fontSize: "14px",
        color: "var(--color-text-secondary)",
        lineHeight: 1.6,
      }}>
        {result.snippet}
      </p>

      {/* Footer row: score + date */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 2 }}>
        {showScore && (
          <span style={{ fontSize: "12px", color: "var(--color-text-tertiary)" }}>
            Score: <strong style={{ fontWeight: 500, color: "var(--color-text-secondary)" }}>
              {result.score.toFixed(2)}
            </strong>
          </span>
        )}
        <span style={{ fontSize: "12px", color: "var(--color-text-tertiary)" }}>
          {new Date(result.created_at).toLocaleDateString(undefined, {
            year: "numeric", month: "short", day: "numeric"
          })}
        </span>
      </div>
    </div>
  );
}

/* ─── Main component ─────────────────────────────────────────────────── */

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [showScore, setShowScore] = useState(false);

  const [results, setResults] = useState(null);  // null = not yet searched
  const [meta, setMeta] = useState(null);         // { page, total_results, total_pages, query }
  const [currentPage, setCurrentPage] = useState(1);

  const [loading, setLoading] = useState(false);
  const [inlineError, setInlineError] = useState("");  // validation errors
  const [apiError, setApiError] = useState("");        // server errors

  /* ── fetch results ───────────────────────────────────────────────── */
  const fetchResults = useCallback(async (searchQuery, page) => {
    setLoading(true);
    setApiError("");
    setResults(null);
    setMeta(null);

    try {
      const params = new URLSearchParams({ q: searchQuery, page });
      if (sourceFilter) params.set("source", sourceFilter);

      const res = await fetch(`${BASE_URL}/api/search?${params}`);
      const data = await res.json();

      if (!res.ok) {
        // Structured error from API
        const msg = data?.error?.message || "An unexpected error occurred.";
        setApiError(msg);
      } else {
        setResults(data.results);
        setMeta({
          page: data.page,
          total_results: data.total_results,
          total_pages: data.total_pages,
          query: data.query,
        });
      }
    } catch {
      setApiError("Could not reach the server. Please check your connection.");
    } finally {
      setLoading(false);
    }
  }, [sourceFilter]);

  /* ── submit handler ──────────────────────────────────────────────── */
  const handleSearch = (page = 1) => {
    // Client-side validation
    if (query.trim().length < 2) {
      setInlineError("Query must be at least 2 characters.");
      return;
    }
    if (query.trim().length > 200) {
      setInlineError("Query must be under 200 characters.");
      return;
    }
    setInlineError("");
    setCurrentPage(page);
    fetchResults(query.trim(), page);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") handleSearch(1);
  };

  const handlePageChange = (newPage) => {
    setCurrentPage(newPage);
    fetchResults(query.trim(), newPage);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  /* ── render ──────────────────────────────────────────────────────── */
  return (
    <div style={{
      maxWidth: 720,
      margin: "0 auto",
      padding: "2rem 1rem",
      fontFamily: "var(--font-sans)",
    }}>

      {/* Page heading */}
      <div style={{ marginBottom: "1.5rem" }}>
        <h1 style={{
          fontSize: 22,
          fontWeight: 500,
          margin: "0 0 4px",
          color: "var(--color-text-primary)",
        }}>
          Document search
        </h1>
        <p style={{
          fontSize: 14,
          color: "var(--color-text-secondary)",
          margin: 0,
        }}>
          Full-text search across all indexed documents
        </p>
      </div>

      {/* Search bar row */}
      <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (inlineError) setInlineError("");
          }}
          onKeyDown={handleKeyDown}
          placeholder="Search documents…"
          maxLength={200}
          aria-label="Search query"
          style={{ flex: 1, fontSize: 15 }}
        />
        <button
          onClick={() => handleSearch(1)}
          disabled={loading}
          style={{ minWidth: 88, fontSize: 14, opacity: loading ? 0.6 : 1 }}
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </div>

      {/* Filter + options row */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        marginBottom: "1.25rem",
        flexWrap: "wrap",
      }}>
        <label style={{ fontSize: 13, color: "var(--color-text-secondary)", display: "flex", alignItems: "center", gap: 6 }}>
          Source
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            style={{ fontSize: 13 }}
          >
            <option value="">All</option>
            <option value="static">Static</option>
            <option value="uploaded">Uploaded</option>
          </select>
        </label>

        <label style={{ fontSize: 13, color: "var(--color-text-secondary)", display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={showScore}
            onChange={(e) => setShowScore(e.target.checked)}
          />
          Show relevance scores
        </label>
      </div>

      {/* Inline validation error */}
      {inlineError && (
        <p style={{
          fontSize: 13,
          color: "var(--color-text-danger)",
          background: "var(--color-background-danger)",
          border: "0.5px solid var(--color-border-danger)",
          borderRadius: "var(--border-radius-md)",
          padding: "8px 12px",
          margin: "0 0 1rem",
        }}>
          {inlineError}
        </p>
      )}

      {/* API error */}
      {apiError && (
        <p style={{
          fontSize: 13,
          color: "var(--color-text-danger)",
          background: "var(--color-background-danger)",
          border: "0.5px solid var(--color-border-danger)",
          borderRadius: "var(--border-radius-md)",
          padding: "8px 12px",
          margin: "0 0 1rem",
        }}>
          {apiError}
        </p>
      )}

      {/* Loading spinner */}
      {loading && <Spinner />}

      {/* Results */}
      {!loading && results !== null && (
        <>
          {/* Result count summary */}
          {meta && results.length > 0 && (
            <p style={{ fontSize: 13, color: "var(--color-text-secondary)", margin: "0 0 1rem" }}>
              {meta.total_results} result{meta.total_results !== 1 ? "s" : ""} for{" "}
              <strong style={{ fontWeight: 500, color: "var(--color-text-primary)" }}>
                "{meta.query}"
              </strong>
            </p>
          )}

          {/* No results */}
          {results.length === 0 && (
            <div style={{
              textAlign: "center",
              padding: "3rem 1rem",
              color: "var(--color-text-secondary)",
              fontSize: 15,
            }}>
              No results found.
            </div>
          )}

          {/* Result cards */}
          {results.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {results.map((r) => (
                <ResultCard key={r.doc_id} result={r} showScore={showScore} />
              ))}
            </div>
          )}

          {/* Pagination */}
          {meta && meta.total_pages > 1 && (
            <div style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 16,
              marginTop: "1.5rem",
            }}>
              <button
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage <= 1}
                style={{ fontSize: 13, opacity: currentPage <= 1 ? 0.4 : 1 }}
              >
                ← Previous
              </button>

              <span style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>
                Page {currentPage} of {meta.total_pages}
              </span>

              <button
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage >= meta.total_pages}
                style={{ fontSize: 13, opacity: currentPage >= meta.total_pages ? 0.4 : 1 }}
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}