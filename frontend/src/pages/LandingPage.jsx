import React from 'react';
import { useNavigate } from 'react-router-dom';
import appScreenshot from '../assets/app-screenshot.png';

const LandingPage = () => {
  const navigate = useNavigate();

  const handleScrollToFeatures = (e) => {
    e.preventDefault();
    const section = document.getElementById('features');
    if (section) {
      section.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <>
      <div className="landing-container">
        {/* HEADER */}
        <header className="landing-header">
          <div className="logo">Findly</div>
          <button
            className="sign-in-btn"
            onClick={() => navigate('/auth')}
          >
            Sign In
          </button>
        </header>

        {/* HERO SECTION */}
        <section id="hero" className="hero-section">
          <h1 className="hero-title">
            Find anything in your documents — instantly.
          </h1>

          <p className="hero-subtitle">
            Upload your files. Search with intelligence. Powered by TF-IDF ranking.
          </p>

          <div className="hero-buttons">
            <button
              className="btn-primary"
              onClick={() => navigate('/auth')}
            >
              Get Started — Sign Up
            </button>

            <button
              className="btn-secondary"
              onClick={() => navigate('/search')}
            >
              Try Search
            </button>
          </div>

          <a href="#features" className="learn-more" onClick={handleScrollToFeatures}>
            Learn More
          </a>

          <div className="hero-image-wrapper">
            <img
              src={appScreenshot}
              alt="Findly search interface"
              className="hero-image"
            />
          </div>
        </section>

        {/* FEATURES SECTION */}
        <section id="features" className="features-section">
          <h2 className="features-title">Why Findly?</h2>

          <div className="features-grid">
            <div className="feature-card">
              <div className="icon" align="center">🔍</div>
              <h3>Inverted Index</h3>
              <p>
                Blazing-fast lookup across thousands of documents using a purpose-built inverted index.
              </p>
            </div>

            <div className="feature-card">
              <div className="icon" align="center">📊</div>
              <h3>TF-IDF Ranking</h3>
              <p>
                Results ranked by relevance, not recency — the same algorithm powering real search engines.
              </p>
            </div>

            <div className="feature-card">
              <div className="icon" align="center">📤</div>
              <h3>Upload Your Docs</h3>
              <p>
                Upload TXT or PDF files and make them instantly searchable alongside the existing dataset.
              </p>
            </div>
          </div>
        </section>

        {/* FOOTER */}
        <footer className="landing-footer">
          <p>Findly — Built with FastAPI, React, and TF-IDF ranking</p>
          <a href="https://github.com/AdarshT100/search-engine.git" className="github-link">
            GitHub
          </a>

          <p>© 2026 Findly</p>
        </footer>
      </div>

      {/* STYLES */}
      <style>{`
        .landing-container {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }

        /* HEADER */
        .landing-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 20px 40px;
          background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        }

        .logo {
          color: white;
          font-weight: bold;
          font-size: 24px;
        }

        .sign-in-btn {
          background: transparent;
          border: 1px solid white;
          color: white;
          padding: 8px 16px;
          border-radius: 6px;
          cursor: pointer;
        }

        /* HERO */
        .hero-section {
          text-align: center;
          padding: 80px 20px 60px;
          background-image:
            radial-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
            linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
          background-size: 28px 28px, 100% 100%;
          color: white;
        }

        .hero-title {
          font-size: 48px;
          font-weight: bold;
          margin-bottom: 20px;
        }

        .hero-subtitle {
          font-size: 18px;
          color: #A5B4FC;
          max-width: 560px;
          margin: 0 auto 30px;
        }

        .hero-buttons {
          display: flex;
          justify-content: center;
          gap: 16px;
          margin-bottom: 20px;
        }

        .btn-primary {
          background: white;
          color: #1a1a2e;
          padding: 12px 20px;
          border: none;
          border-radius: 8px;
          cursor: pointer;
          font-weight: 600;
        }

        .btn-secondary {
          background: transparent;
          border: 1px solid white;
          color: white;
          padding: 12px 20px;
          border-radius: 8px;
          cursor: pointer;
        }

        .learn-more {
          display: block;
          margin-bottom: 40px;
          color: white;
          font-size: 14px;
          text-decoration: none;
        }

        .hero-image-wrapper {
          display: flex;
          justify-content: center;
        }

        .hero-image {
          max-width: 820px;
          width: 100%;
          border-radius: 12px;
          box-shadow: 0 24px 60px rgba(0, 0, 0, 0.4);
        }

        /* FEATURES */
        .features-section {
          background: #FFFFFF;
          padding: 80px 20px;
          text-align: center;
        }

        .features-title {
          font-size: 32px;
          margin-bottom: 40px;
          color: #1a1a2e;
        }

        .features-grid {
          display: flex;
          justify-content: center;
          gap: 24px;
          flex-wrap: wrap;
        }

        .feature-card {
          border: 1px solid #E5E7EB;
          border-radius: 12px;
          padding: 32px;
          max-width: 300px;
          transition: box-shadow 0.2s ease;
          text-align: left;
        }

        .feature-card:hover {
          box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }

        .feature-card .icon {
          font-size: 28px;
          margin-bottom: 12px;
          text-align: center;
        }

        .feature-card h3 {
          margin-bottom: 10px;
          color: #1a1a2e;
        }

        .feature-card p {
          color: #374151;
          font-size: 14px;
        }

        /* FOOTER */
        .landing-footer {
          background: #1a1a2e;
          color: white;
          text-align: center;
          padding: 40px 20px;
          margin: 6px 0;
        }

        .github-link {
          color: #A5B4FC;
          display: block;
          margin: 10px 0;
          text-decoration: none;
        }

        /* RESPONSIVE */
        @media (max-width: 768px) {
          .hero-title {
            font-size: 32px;
          }

          .hero-buttons {
            flex-direction: column;
            align-items: center;
          }

          .feature-card {
            width: 100%;
            max-width: 100%;
          }
        }
      `}</style>
    </>
  );
};

export default LandingPage;