import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = {
  nav: {
    backgroundColor: "#FFFFFF",
    borderBottom: "1px solid #E5E7EB",
    padding: "0 24px",
    height: "60px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    position: "sticky",
    top: 0,
    zIndex: 100,
  },
  logo: {
    fontSize: "20px",
    fontWeight: "700",
    color: "#1a1a2e",
    textDecoration: "none",
    letterSpacing: "-0.3px",
  },
  navLinks: {
    display: "flex",
    alignItems: "center",
    gap: "24px",
    listStyle: "none",
    margin: 0,
    padding: 0,
  },
  link: {
    fontSize: "14px",
    fontWeight: "500",
    color: "#374151",
    textDecoration: "none",
  },
  userEmail: {
    fontSize: "14px",
    color: "#6B7280",
    maxWidth: "200px",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  logoutBtn: {
    fontSize: "14px",
    fontWeight: "500",
    color: "#FFFFFF",
    backgroundColor: "#1a1a2e",
    border: "none",
    borderRadius: "6px",
    padding: "7px 14px",
    cursor: "pointer",
  },
};

// ─── Component ────────────────────────────────────────────────────────────────

export default function Navbar({ showNav }) {
  const navigate = useNavigate();
  const { isLoggedIn, userEmail, logout } = useAuth();

  // Hidden on landing page
  if (!showNav) return null;

  function handleLogout() {
    logout();
    navigate("/");
  }

  return (
    <nav style={styles.nav}>
      {/* Logo */}
      <Link to="/search" style={styles.logo}>
        Findly
      </Link>

      {/* Nav links */}
      <ul style={styles.navLinks}>
        <li>
          <Link to="/search" style={styles.link}>
            Search
          </Link>
        </li>

        {isLoggedIn ? (
          <>
            <li>
              <Link to="/upload" style={styles.link}>
                Upload
              </Link>
            </li>
            <li>
              <span style={styles.userEmail} title={userEmail}>
                {userEmail}
              </span>
            </li>
            <li>
              <button style={styles.logoutBtn} onClick={handleLogout}>
                Logout
              </button>
            </li>
          </>
        ) : (
          <li>
            <Link to="/auth" style={styles.link}>
              Login / Register
            </Link>
          </li>
        )}
      </ul>
    </nav>
  );
}