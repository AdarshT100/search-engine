import { useState, useEffect, useRef } from "react";

const BASE_URL = import.meta.env.VITE_API_BASE_URL;

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB
const ACCEPTED_TYPES = ["text/plain", "application/pdf"];
const ACCEPTED_EXTENSIONS = [".txt", ".pdf"];

/* ─── Helpers ─────────────────────────────────────────────────────── */

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric", month: "short", day: "numeric",
  });
}

/* ─── Sub-components ──────────────────────────────────────────────── */

function StatusBanner({ type, message }) {
  if (!message) return null;
  const colorMap = {
    success: {
      color: "var(--color-text-success)",
      bg: "var(--color-background-success)",
      border: "var(--color-border-success)",
    },
    error: {
      color: "var(--color-text-danger)",
      bg: "var(--color-background-danger)",
      border: "var(--color-border-danger)",
    },
    info: {
      color: "var(--color-text-info)",
      bg: "var(--color-background-info)",
      border: "var(--color-border-info)",
    },
  };
  const c = colorMap[type] || colorMap.info;
  return (
    <p style={{
      fontSize: 13,
      color: c.color,
      background: c.bg,
      border: `0.5px solid ${c.border}`,
      borderRadius: "var(--border-radius-md)",
      padding: "8px 12px",
      margin: "0 0 1rem",
    }}>
      {message}
    </p>
  );
}

function FileTypeBadge({ fileType }) {
  const isPdf = fileType === "pdf";
  return (
    <span style={{
      display: "inline-block",
      fontSize: 11,
      fontWeight: 500,
      padding: "2px 7px",
      borderRadius: "999px",
      background: isPdf ? "#FAECE7" : "#E1F5EE",
      color: isPdf ? "#993C1D" : "#085041",
      border: isPdf ? "0.5px solid #F5C4B3" : "0.5px solid #9FE1CB",
      textTransform: "uppercase",
      letterSpacing: "0.04em",
    }}>
      {fileType}
    </span>
  );
}

function DocumentRow({ doc, onDelete, deleting }) {
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: 12,
      padding: "10px 1.25rem",
      borderBottom: "0.5px solid var(--color-border-tertiary)",
    }}>
      {/* File type badge */}
      <FileTypeBadge fileType={doc.file_type} />

      {/* Title + meta */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{
          margin: 0,
          fontSize: 14,
          fontWeight: 500,
          color: "var(--color-text-primary)",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}>
          {doc.title}
        </p>
        <p style={{
          margin: 0,
          fontSize: 12,
          color: "var(--color-text-tertiary)",
        }}>
          {formatBytes(doc.file_size)} · {formatDate(doc.uploaded_at)}
        </p>
      </div>

      {/* Delete button */}
      <button
        onClick={() => onDelete(doc.doc_id)}
        disabled={deleting === doc.doc_id}
        aria-label={`Delete ${doc.title}`}
        style={{
          fontSize: 12,
          padding: "4px 10px",
          color: "var(--color-text-danger)",
          borderColor: "var(--color-border-danger)",
          background: "transparent",
          opacity: deleting === doc.doc_id ? 0.5 : 1,
          flexShrink: 0,
        }}
      >
        {deleting === doc.doc_id ? "Deleting…" : "Delete"}
      </button>
    </div>
  );
}

/* ─── Main component ─────────────────────────────────────────────── */
/*
  Props:
    accessToken  — JWT access token string from parent/context (required for
                   upload + document list endpoints). If absent, a warning
                   is shown and the upload form is disabled.
*/
export default function UploadPage({ accessToken }) {
  // File selection
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileError, setFileError] = useState("");      // client-side file validation
  const fileInputRef = useRef(null);

  // Upload state
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null); // { type, message }

  // Documents list
  const [documents, setDocuments] = useState([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [docsError, setDocsError] = useState("");
  const [deletingId, setDeletingId] = useState(null);  // doc_id currently being deleted

  const authHeader = { Authorization: `Bearer ${accessToken}` };

  /* ── fetch user's documents ──────────────────────────────────────── */

  const fetchDocuments = async () => {
    if (!accessToken) return;
    setDocsLoading(true);
    setDocsError("");
    try {
      const res = await fetch(`${BASE_URL}/api/documents`, { headers: authHeader });
      const data = await res.json();
      if (!res.ok) {
        setDocsError(data?.error?.message || "Could not load documents.");
      } else {
        setDocuments(data.documents || []);
      }
    } catch {
      setDocsError("Could not reach the server.");
    } finally {
      setDocsLoading(false);
    }
  };

  // Load documents on mount and whenever the token changes
  useEffect(() => {
    fetchDocuments();
  }, [accessToken]);

  /* ── file selection & client validation ──────────────────────────── */

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    setUploadStatus(null);
    setFileError("");
    setSelectedFile(null);

    if (!file) return;

    // Validate MIME type
    if (!ACCEPTED_TYPES.includes(file.type)) {
      setFileError("Only .txt and .pdf files are accepted.");
      return;
    }

    // Validate size (client-side pre-check — server enforces this too)
    if (file.size > MAX_FILE_SIZE) {
      setFileError(`File is too large (${formatBytes(file.size)}). Maximum size is 5 MB.`);
      return;
    }

    setSelectedFile(file);
  };

  /* ── upload ──────────────────────────────────────────────────────── */

  const handleUpload = async () => {
    if (!selectedFile || uploading) return;

    setUploading(true);
    setUploadStatus(null);

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const res = await fetch(`${BASE_URL}/api/documents/upload`, {
        method: "POST",
        headers: authHeader,  // do NOT set Content-Type — browser sets it with boundary
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        // Map known error codes to friendly messages
        const code = data?.error?.code;
        const serverMsg = data?.error?.message || "Upload failed. Please try again.";

        const friendlyMsg = {
          SCANNED_PDF: "This PDF has no text layer (scanned/image PDF). Only digital PDFs are supported.",
          FILE_TOO_LARGE: "File exceeds the 5 MB limit.",
          RATE_LIMIT_EXCEEDED: "You've reached the limit of 10 uploads per day.",
          INVALID_FILE_TYPE: "Only .txt and .pdf files are supported.",
          INVALID_TOKEN: "Your session has expired. Please log in again.",
        }[code] || serverMsg;

        setUploadStatus({ type: "error", message: friendlyMsg });
      } else {
        // Success
        setUploadStatus({ type: "success", message: "Document indexed and searchable." });
        setSelectedFile(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
        // Refresh the document list so the new file appears immediately
        fetchDocuments();
      }
    } catch {
      setUploadStatus({ type: "error", message: "Could not reach the server. Please check your connection." });
    } finally {
      setUploading(false);
    }
  };

  /* ── delete ──────────────────────────────────────────────────────── */

  const handleDelete = async (docId) => {
    if (deletingId) return;
    setDeletingId(docId);

    try {
      const res = await fetch(`${BASE_URL}/api/documents/${docId}`, {
        method: "DELETE",
        headers: authHeader,
      });

      if (!res.ok) {
        const data = await res.json();
        setDocsError(data?.error?.message || "Could not delete document.");
      } else {
        // Remove from local list immediately — no need to refetch
        setDocuments((prev) => prev.filter((d) => d.doc_id !== docId));
      }
    } catch {
      setDocsError("Could not reach the server.");
    } finally {
      setDeletingId(null);
    }
  };

  /* ── render ──────────────────────────────────────────────────────── */

  return (
    <div style={styles.page}>

      {/* ── Upload section ────────────────────────────────────────── */}
      <section style={styles.card}>
        <h1 style={styles.heading}>Upload a document</h1>
        <p style={styles.subheading}>
          Supported formats: .txt and .pdf (digital only, max 5 MB)
        </p>

        {/* No token warning */}
        {!accessToken && (
          <StatusBanner type="error" message="You must be logged in to upload documents." />
        )}

        {/* File input */}
        <div style={styles.fieldGroup}>
          <label style={styles.label} htmlFor="file-input">Choose file</label>
          <input
            id="file-input"
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_EXTENSIONS.join(",")}
            onChange={handleFileChange}
            disabled={!accessToken || uploading}
            style={{ fontSize: 13, cursor: accessToken ? "pointer" : "not-allowed" }}
          />
        </div>

        {/* File validation error */}
        {fileError && <StatusBanner type="error" message={fileError} />}

        {/* Selected file preview */}
        {selectedFile && !fileError && (
          <div style={styles.filePreview}>
            <FileTypeBadge fileType={selectedFile.name.endsWith(".pdf") ? "pdf" : "txt"} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={styles.fileName}>{selectedFile.name}</p>
              <p style={styles.fileMeta}>{formatBytes(selectedFile.size)}</p>
            </div>
          </div>
        )}

        {/* Upload status banner (success / error from server) */}
        {uploadStatus && (
          <StatusBanner type={uploadStatus.type} message={uploadStatus.message} />
        )}

        {/* Upload button */}
        <button
          onClick={handleUpload}
          disabled={!selectedFile || uploading || !accessToken}
          style={{
            ...styles.uploadBtn,
            opacity: (!selectedFile || uploading || !accessToken) ? 0.5 : 1,
            cursor: (!selectedFile || uploading || !accessToken) ? "not-allowed" : "pointer",
          }}
        >
          {uploading ? "Uploading…" : "Upload and index"}
        </button>

        {/* Uploading indicator */}
        {uploading && (
          <p style={{ fontSize: 13, color: "var(--color-text-secondary)", margin: "8px 0 0", textAlign: "center" }}>
            Extracting text and building index…
          </p>
        )}
      </section>

      {/* ── Documents list ────────────────────────────────────────── */}
      <section style={{ ...styles.card, padding: 0, overflow: "hidden" }}>

        {/* Section header */}
        <div style={{ padding: "1rem 1.25rem", borderBottom: "0.5px solid var(--color-border-tertiary)" }}>
          <h2 style={styles.sectionHeading}>Your documents</h2>
          {!docsLoading && documents.length > 0 && (
            <p style={styles.docCount}>
              {documents.length} document{documents.length !== 1 ? "s" : ""}
            </p>
          )}
        </div>

        {/* Loading */}
        {docsLoading && (
          <p style={styles.listPlaceholder}>Loading…</p>
        )}

        {/* Error */}
        {docsError && !docsLoading && (
          <div style={{ padding: "0 1.25rem 1rem" }}>
            <StatusBanner type="error" message={docsError} />
          </div>
        )}

        {/* No documents */}
        {!docsLoading && !docsError && documents.length === 0 && (
          <p style={styles.listPlaceholder}>
            No documents uploaded yet.
          </p>
        )}

        {/* Document rows */}
        {!docsLoading && documents.map((doc) => (
          <DocumentRow
            key={doc.doc_id}
            doc={doc}
            onDelete={handleDelete}
            deleting={deletingId}
          />
        ))}
      </section>

    </div>
  );
}

/* ─── Styles ─────────────────────────────────────────────────────── */

const styles = {
  page: {
    maxWidth: 640,
    margin: "0 auto",
    padding: "2rem 1rem",
    fontFamily: "var(--font-sans)",
    display: "flex",
    flexDirection: "column",
    gap: "1.5rem",
  },
  card: {
    background: "var(--color-background-primary)",
    border: "0.5px solid var(--color-border-tertiary)",
    borderRadius: "var(--border-radius-lg)",
    padding: "1.5rem 1.25rem",
    display: "flex",
    flexDirection: "column",
    gap: 0,
  },
  heading: {
    fontSize: 22,
    fontWeight: 500,
    margin: "0 0 4px",
    color: "var(--color-text-primary)",
  },
  subheading: {
    fontSize: 13,
    color: "var(--color-text-secondary)",
    margin: "0 0 1.25rem",
  },
  sectionHeading: {
    fontSize: 16,
    fontWeight: 500,
    margin: 0,
    color: "var(--color-text-primary)",
  },
  docCount: {
    fontSize: 12,
    color: "var(--color-text-tertiary)",
    margin: "2px 0 0",
  },
  fieldGroup: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
    marginBottom: "1rem",
  },
  label: {
    fontSize: 13,
    fontWeight: 500,
    color: "var(--color-text-secondary)",
  },
  filePreview: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    background: "var(--color-background-secondary)",
    border: "0.5px solid var(--color-border-tertiary)",
    borderRadius: "var(--border-radius-md)",
    padding: "10px 12px",
    marginBottom: "1rem",
  },
  fileName: {
    margin: 0,
    fontSize: 13,
    fontWeight: 500,
    color: "var(--color-text-primary)",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  fileMeta: {
    margin: 0,
    fontSize: 12,
    color: "var(--color-text-tertiary)",
  },
  uploadBtn: {
    width: "100%",
    fontSize: 14,
    fontWeight: 500,
    padding: "9px 0",
    marginTop: 4,
  },
  listPlaceholder: {
    fontSize: 14,
    color: "var(--color-text-tertiary)",
    textAlign: "center",
    padding: "2rem 1rem",
    margin: 0,
  },
};