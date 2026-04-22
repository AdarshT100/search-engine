import { useState } from "react";

const BASE_URL = import.meta.env.VITE_API_BASE_URL;

/* ─── Prop contract ───────────────────────────────────────────────────
   AuthPage expects two optional props from a parent / router:
     onAuthSuccess(tokens)  — called with { access_token, refresh_token }
                              after a successful login. Parent stores tokens
                              in app-level state and renders UploadPage.
     navigateToUpload()     — if you are using React Router, pass
                              () => navigate('/upload') here. If omitted,
                              AuthPage shows an inline "Go to Upload" button
                              instead of redirecting.
   ─────────────────────────────────────────────────────────────────── */

export default function AuthPage({ onAuthSuccess, navigateToUpload }) {
  // "login" | "register"
  const [mode, setMode] = useState("login");

  // Form fields
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // UI state
  const [loading, setLoading] = useState(false);
  const [fieldError, setFieldError] = useState("");   // client-side validation
  const [apiError, setApiError] = useState("");        // server error message
  const [successMsg, setSuccessMsg] = useState("");    // post-register confirmation

  // Tokens stored in memory only — never written to localStorage
  const [tokens, setTokens] = useState(null);          // { access_token, refresh_token }

  /* ── helpers ────────────────────────────────────────────────────── */

  const resetMessages = () => {
    setFieldError("");
    setApiError("");
    setSuccessMsg("");
  };

  const switchMode = (newMode) => {
    setMode(newMode);
    setEmail("");
    setPassword("");
    resetMessages();
    setTokens(null);
  };

  // Basic client-side validation before hitting the network
  const validate = () => {
    if (!email.trim()) return "Email is required.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) return "Enter a valid email address.";
    if (!password) return "Password is required.";
    if (mode === "register" && password.length < 8) return "Password must be at least 8 characters.";
    return null;
  };

  /* ── submit ─────────────────────────────────────────────────────── */

  const handleSubmit = async () => {
    resetMessages();

    const validationError = validate();
    if (validationError) {
      setFieldError(validationError);
      return;
    }

    setLoading(true);

    const endpoint = mode === "login"
      ? `${BASE_URL}/api/auth/login`
      : `${BASE_URL}/api/auth/register`;

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });

      const data = await res.json();

      if (!res.ok) {
        // Structured API error envelope: { error: { code, message, status } }
        setApiError(data?.error?.message || "Something went wrong. Please try again.");
        return;
      }

      if (mode === "register") {
        // Registration succeeded — prompt user to log in
        setSuccessMsg("Account created! You can now log in.");
        setMode("login");
        setPassword("");
      } else {
        // Login succeeded — store tokens in memory only
        const received = {
          access_token: data.access_token,
          refresh_token: data.refresh_token,
        };
        setTokens(received);

        // Notify parent so it can store tokens at app level
        if (onAuthSuccess) onAuthSuccess(received);

        // Navigate if a router function was provided
        if (navigateToUpload) navigateToUpload();
      }
    } catch {
      setApiError("Could not reach the server. Please check your connection.");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") handleSubmit();
  };

  /* ── logged-in state (no router provided) ────────────────────────── */
if (tokens && !navigateToUpload) {
  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <p style={{ ...styles.successBanner, marginBottom: "1.25rem" }}>
          Logged in successfully.
        </p>
        <p style={{ fontSize: 14, color: "var(--color-text-secondary)", margin: "0 0 1rem" }}>
          Your session is active. Tokens are held in memory only.
        </p>
        {/* ✅ FIXED: was <a href="/upload"> which caused full page reload */}
        <button
          style={styles.uploadLink}
          onClick={() => {
            if (onAuthSuccess) onAuthSuccess(tokens);
          }}
        >
          Go to Upload →
        </button>
      </div>
    </div>
  );
}

  /* ── main form ───────────────────────────────────────────────────── */

  return (
    <div style={styles.page}>
      <div style={styles.card}>

        {/* Heading */}
        <h1 style={styles.heading}>
          {mode === "login" ? "Sign in" : "Create account"}
        </h1>

        {/* Mode toggle */}
        <div style={styles.toggleRow}>
          <button
            onClick={() => switchMode("login")}
            style={mode === "login" ? styles.toggleActive : styles.toggleInactive}
          >
            Sign in
          </button>
          <button
            onClick={() => switchMode("register")}
            style={mode === "register" ? styles.toggleActive : styles.toggleInactive}
          >
            Register
          </button>
        </div>

        {/* Post-register success */}
        {successMsg && (
          <p style={styles.successBanner}>{successMsg}</p>
        )}

        {/* Fields */}
        <div style={styles.fieldGroup}>
          <label style={styles.label} htmlFor="auth-email">Email</label>
          <input
            id="auth-email"
            type="email"
            value={email}
            onChange={(e) => { setEmail(e.target.value); resetMessages(); }}
            onKeyDown={handleKeyDown}
            placeholder="you@example.com"
            autoComplete="email"
            style={styles.input}
          />
        </div>

        <div style={styles.fieldGroup}>
          <label style={styles.label} htmlFor="auth-password">
            Password
            {mode === "register" && (
              <span style={styles.hint}> — min 8 characters</span>
            )}
          </label>
          <input
            id="auth-password"
            type="password"
            value={password}
            onChange={(e) => { setPassword(e.target.value); resetMessages(); }}
            onKeyDown={handleKeyDown}
            placeholder={mode === "register" ? "Min 8 characters" : "Your password"}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            style={styles.input}
          />
        </div>

        {/* Validation error */}
        {fieldError && <p style={styles.errorMsg}>{fieldError}</p>}

        {/* API error */}
        {apiError && <p style={styles.errorMsg}>{apiError}</p>}

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={loading}
          style={{ ...styles.submitBtn, opacity: loading ? 0.6 : 1 }}
        >
          {loading
            ? (mode === "login" ? "Signing in…" : "Creating account…")
            : (mode === "login" ? "Sign in" : "Create account")}
        </button>

        {/* Mode switch hint */}
        <p style={styles.switchHint}>
          {mode === "login"
            ? <>No account?{" "}
                <button style={styles.textLink} onClick={() => switchMode("register")}>
                  Register
                </button>
              </>
            : <>Already have an account?{" "}
                <button style={styles.textLink} onClick={() => switchMode("login")}>
                  Sign in
                </button>
              </>
          }
        </p>

      </div>
    </div>
  );
}

/* ─── Styles ─────────────────────────────────────────────────────────── */

const styles = {
  page: {
    display: "flex",
    justifyContent: "center",
    alignItems: "flex-start",
    padding: "3rem 1rem",
    fontFamily: "var(--font-sans)",
    minHeight: "60vh",
  },
  card: {
    width: "100%",
    maxWidth: 420,
    background: "var(--color-background-primary)",
    border: "0.5px solid var(--color-border-tertiary)",
    borderRadius: "var(--border-radius-lg)",
    padding: "2rem 1.75rem",
    display: "flex",
    flexDirection: "column",
    gap: 0,
  },
  heading: {
    fontSize: 22,
    fontWeight: 500,
    margin: "0 0 1.25rem",
    color: "var(--color-text-primary)",
  },
  toggleRow: {
    display: "flex",
    gap: 8,
    marginBottom: "1.5rem",
  },
  toggleActive: {
    flex: 1,
    fontSize: 13,
    fontWeight: 500,
    padding: "7px 0",
    borderRadius: "var(--border-radius-md)",
    border: "0.5px solid var(--color-border-primary)",
    background: "var(--color-background-secondary)",
    color: "var(--color-text-primary)",
    cursor: "pointer",
  },
  toggleInactive: {
    flex: 1,
    fontSize: 13,
    fontWeight: 400,
    padding: "7px 0",
    borderRadius: "var(--border-radius-md)",
    border: "0.5px solid var(--color-border-tertiary)",
    background: "transparent",
    color: "var(--color-text-secondary)",
    cursor: "pointer",
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
  hint: {
    fontWeight: 400,
    color: "var(--color-text-tertiary)",
  },
  input: {
    fontSize: 14,
    width: "100%",
    boxSizing: "border-box",
  },
  errorMsg: {
    fontSize: 13,
    color: "var(--color-text-danger)",
    background: "var(--color-background-danger)",
    border: "0.5px solid var(--color-border-danger)",
    borderRadius: "var(--border-radius-md)",
    padding: "8px 12px",
    margin: "0 0 1rem",
  },
  successBanner: {
    fontSize: 13,
    color: "var(--color-text-success)",
    background: "var(--color-background-success)",
    border: "0.5px solid var(--color-border-success)",
    borderRadius: "var(--border-radius-md)",
    padding: "8px 12px",
    margin: "0 0 1rem",
  },
  submitBtn: {
    width: "100%",
    fontSize: 14,
    fontWeight: 500,
    padding: "9px 0",
    marginTop: 4,
    cursor: "pointer",
  },
  switchHint: {
    fontSize: 13,
    color: "var(--color-text-secondary)",
    textAlign: "center",
    margin: "1rem 0 0",
  },
  textLink: {
    background: "none",
    border: "none",
    padding: 0,
    fontSize: 13,
    color: "var(--color-text-info)",
    cursor: "pointer",
    textDecoration: "underline",
  },
  uploadLink: {
    display: "inline-block",
    fontSize: 14,
    color: "var(--color-text-info)",
    textDecoration: "none",
  },
};