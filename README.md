# Findly — Intelligent Document Search Engine

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19.2-61DAFB?logo=react)](https://react.dev)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python)](https://python.org)

Search through thousands of documents in milliseconds. Upload PDFs and TXT files, get instantly ranked results using **TF-IDF** — the same algorithm powering Google and Bing.

**Built for developers.** Full-text search with an inverted index, JWT auth, and a polished React UI.

• [📚 Docs](#api-endpoints) • [🐛 Issues](https://github.com/AdarshT100/search-engine/issues)

---

## ⚡ Quick Start

### Backend (60 seconds)

```bash
git clone https://github.com/AdarshT100/search-engine.git
cd search-engine

# Create .env
cat > .env << EOF
DATABASE_URL=postgresql://user:password@localhost:5432/findly_db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=$(openssl rand -hex 32)
ALLOWED_ORIGINS=http://localhost:5173
EOF

# Setup database & run
pip install -r requirements.txt
createdb findly_db
alembic upgrade head
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/docs` for interactive API docs.

### Frontend (30 seconds)

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **TF-IDF Ranking** | Cosine similarity scoring — results ranked by relevance, not recency |
| **Inverted Index** | Redis-cached, PostgreSQL-backed full-text lookup |
| **JWT Auth** | Secure register/login/refresh with bcrypt password hashing |
| **PDF + TXT Upload** | Automatic text extraction, 5 MB limit, 10/day rate limiting |
| **Real-Time Indexing** | Documents searchable immediately upon upload |
| **Public Search** | Query all documents without authentication |
| **Autocomplete** | Prefix-based suggestions from cached index |
| **Smart Preprocessing** | NLTK tokenization, stopword removal, normalization |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│  React Frontend (Vite)                  │
│  ├─ Search, Upload, Auth Pages          │
│  └─ Context-based Auth State            │
└──────────────┬──────────────────────────┘
               │
        ┌──────▼──────────┐
        │  FastAPI Backend │
        └──────┬──────────┘
          │    │    │
    ┌─────▼─┐ ┌─▼─┐ ┌──▼─────┐
    │ Search│ │JWT│ │ Upload  │
    │ Index │ │Auth│ │Ingest  │
    └─┬──┬──┘ └───┘ └────┬────┘
      │  │            │
   ┌──▼──▼─────┬──────▼─────┐
   │ PostgreSQL │  Redis     │
   │ Vectorizer │  Cache +   │
   │ + Docs     │  Rate Limit│
   └────────────┴────────────┘
```

---

## 🚀 How It Works

### Indexing Pipeline
1. PDF/TXT extracted → tokenized → indexed via TF-IDF vectorizer
2. Term frequencies stored in PostgreSQL, cached in Redis (24h TTL)
3. Immediately searchable alongside static dataset

### Search Pipeline
1. Query preprocessed through same NLP pipeline (ensures token consistency)
2. Tokens looked up in Redis/PostgreSQL inverted index
3. Candidate documents merged with OR logic
4. Cosine similarity computed against TF-IDF matrix
5. Results ranked, filtered, paginated (10 per page)
6. Snippets generated from top 150 characters

---

## 📦 Prerequisites

- **Python** 3.9+
- **Node.js** 16+
- **PostgreSQL** 12+
- **Redis** 6+

Optional: AWS S3 for production file storage.

---

## 🔌 API Endpoints

### Authentication (Public)
```
POST   /api/auth/register       Create account
POST   /api/auth/login          Get tokens
POST   /api/auth/refresh        Refresh access token
```

### Search (Public)
```
GET    /api/search?q=term&page=1&source=static|uploaded    Full-text search
GET    /api/autocomplete?prefix=ke                          Suggestions
GET    /health                                              Health check
```

### Documents (Protected — JWT Required)
```
POST   /api/documents/upload    Upload file (5 MB max, 10/day limit)
GET    /api/documents           List user's documents
DELETE /api/documents/{id}      Delete document & cascade cleanup
```

**Error Format:**
```json
{
  "error": {
    "code": "INVALID_FILE_TYPE",
    "message": "Only TXT and PDF files are supported.",
    "status": 422
  }
}
```

---

## 📊 Database

- **users** — Email, password hash, created_at
- **documents** — Title, body, source (static/uploaded), s3_key, user_id
- **index_entries** — Term, doc_id, TF-IDF score, token positions
- **upload_logs** — File metadata for analytics

---

## 🛠️ Development

```bash
# Lint frontend
npm run lint

# Format backend
flake8 app/

# Create database migration
alembic revision --autogenerate -m "description"

# Apply/rollback migrations
alembic upgrade head
alembic downgrade -1
```

---

## 🚢 Production

```bash
# Backend
gunicorn app.main:app -w 4 -b 0.0.0.0:8000

# Frontend
npm run build    # → dist/ folder
npm run preview
```

Use environment variables for secrets (DATABASE_URL, SECRET_KEY, AWS credentials, etc.).

---

## 📚 Tech Stack

**Backend:** FastAPI • SQLAlchemy • PostgreSQL • Redis • Scikit-Learn • PyMuPDF • JWT

**Frontend:** React 19 • React Router • Vite

---

