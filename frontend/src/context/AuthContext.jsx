import { createContext, useContext, useState } from "react";

// ─── Context ─────────────────────────────────────────────────────────────────

const AuthContext = createContext(null);

// ─── Provider ────────────────────────────────────────────────────────────────

export function AuthProvider({ children }) {
  const [accessToken, setAccessToken]   = useState(null);
  const [refreshToken, setRefreshToken] = useState(null);
  const [userEmail, setUserEmail]       = useState(null);

  // Derived — no extra state needed
  const isLoggedIn = accessToken !== null;

  /**
   * login({ access_token, refresh_token }, email)
   * Called by AuthPage after a successful /api/auth/login response.
   */
  function login(tokens, email) {
    setAccessToken(tokens.access_token);
    setRefreshToken(tokens.refresh_token);
    setUserEmail(email);
  }

  /**
   * logout()
   * Called by the Navbar logout button.
   * Clears all auth state — tokens are discarded from memory immediately.
   */
  function logout() {
    setAccessToken(null);
    setRefreshToken(null);
    setUserEmail(null);
  }

  const value = {
    accessToken,
    refreshToken,
    userEmail,
    isLoggedIn,
    login,
    logout,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

// ─── Consumer hook ────────────────────────────────────────────────────────────
/**
 * useAuth()
 * Must be called inside a component wrapped by <AuthProvider>.
 * Throws a clear error if used outside the provider tree.
 */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error("useAuth() must be used inside an <AuthProvider>.");
  }
  return ctx;
}