import { useState } from 'react'
import SearchPage from './pages/SearchPage.jsx'
import AuthPage from './pages/AuthPages.jsx'
import UploadPage from './pages/UploadPage.jsx'

function App() {
  const [page, setPage] = useState('search')
  const [accessToken, setAccessToken] = useState(null)

  // ✅ FIXED: store token AND switch page in one shot
  const handleLogin = (tokens) => {
    setAccessToken(tokens.access_token)
    setPage('upload')
  }

  return (
    <div>
      <nav style={{ padding: '1rem', borderBottom: '1px solid #ccc', display: 'flex', gap: '1rem' }}>
        <button onClick={() => setPage('search')}>Search</button>
        <button onClick={() => setPage('auth')}>Login / Register</button>
        <button onClick={() => setPage('upload')}>Upload</button>
      </nav>

      {page === 'search' && <SearchPage />}
      {page === 'auth' && <AuthPage onAuthSuccess={handleLogin} />}
      {page === 'upload' && <UploadPage accessToken={accessToken} />}
    </div>
  )
}

export default App
