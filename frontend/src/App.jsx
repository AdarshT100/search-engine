/**
 * App.jsx
 * Findly — Search Engine
 *
 * Root component. Wraps the app in AuthProvider and React Router.
 * Renders the Navbar once at the app level; hides it on the landing page (/).
 */

import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';

import Navbar      from './components/Navbar';
import LandingPage from './pages/LandingPage';
import SearchPage  from './pages/SearchPage';
import AuthPage    from './pages/AuthPages';
import UploadPage  from './pages/UploadPage';

/** Routes where the Navbar should be hidden. */
const HIDDEN_NAV_ROUTES = ['/'];

/**
 * AppShell
 * Rendered inside BrowserRouter so it can call useLocation().
 * Determines whether to show the Navbar based on the current route,
 * then renders the route tree.
 */
function AppShell() {
  const location = useLocation();
  const showNav = !HIDDEN_NAV_ROUTES.includes(location.pathname);

  return (
    <>
      <Navbar showNav={showNav} />

      <Routes>
        <Route path="/"       element={<LandingPage />} />
        <Route path="/search" element={<SearchPage />}  />
        <Route path="/auth"   element={<AuthPage />}    />
        <Route path="/upload" element={<UploadPage />}  />
      </Routes>
    </>
  );
}

/**
 * App
 * Top-level component. Provides AuthContext to the entire tree
 * and wraps everything in BrowserRouter.
 */
export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppShell />
      </BrowserRouter>
    </AuthProvider>
  );
}