# 🗺️ Iran Protest Map

A real-time interactive heatmap visualization of protest events in Iran, aggregating data from multiple sources including Telegram channels and RSS feeds. Built with Next.js, FastAPI, and deck.gl.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Next.js](https://img.shields.io/badge/Next.js-16-black)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688)
![PostGIS](https://img.shields.io/badge/PostGIS-15-336791)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)
![Contributors](https://img.shields.io/badge/contributors-welcome-orange.svg)
![Good First Issues](https://img.shields.io/badge/good%20first%20issues-available-blueviolet)

---

## 📑 Table of Contents

- [Features](#-features)
- [Architecture](#️-architecture)
- [Tech Stack](#️-tech-stack)
- [Getting Started](#-getting-started)
- [API Endpoints](#-api-endpoints)
- [Environment Variables](#️-environment-variables)
- [Docker Commands](#-docker-commands)
- [Production Deployment](#-production-deployment)
- [Project Structure](#-project-structure)
- [Contributing](#-contributing)
- [Reporting Issues](#-reporting-issues)
- [Code of Conduct](#️-code-of-conduct)
- [Security](#-security)
- [Community](#-community)
- [License](#-license)

---

## ✨ Features

- **Live Heatmap Visualization** — Real-time heatmap of protest events using deck.gl with intensity-based coloring
- **Verified vs Unverified Events** — Toggle between all reports and verified-only incidents
- **Event Details** — Click any point to view full details including media, source links, and timestamps
- **Persian → English Translation** — Built-in translation for report titles and descriptions
- **Media Support** — Display images and videos from Telegram with native playback
- **Social Sharing** — Share individual reports via Web Share API or clipboard
- **GeoJSON API** — RESTful API serving events as GeoJSON FeatureCollections
- **Automated Ingestion** — Background service to ingest reports from Telegram and RSS feeds

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Map.tsx   │  │ Sidebar.tsx │  │     page.tsx (Home)     │  │
│  │  (deck.gl)  │  │  (Details)  │  │   (State Management)    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  /api/events│  │ /api/stats  │  │    /api/translate       │  │
│  │  (GeoJSON)  │  │  (Counts)   │  │  (Persian → English)    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Ingestion Service                            │   │
│  │   Telegram Channels → Geocoding → PostGIS Database       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL + PostGIS                          │
│         Geospatial database for event storage & queries          │
└─────────────────────────────────────────────────────────────────┘
```

## 🛠️ Tech Stack

### Frontend

- **Next.js 16** — React framework with App Router
- **React 19** — UI library
- **deck.gl** — High-performance WebGL visualization
- **MapLibre GL** — Open-source map rendering
- **Tailwind CSS 4** — Utility-first styling
- **Lucide React** — Icon library
- **date-fns** — Date formatting

### Backend

- **FastAPI** — Modern Python web framework
- **SQLAlchemy 2.0** — ORM with async support
- **GeoAlchemy2** — Geospatial extensions for SQLAlchemy
- **PostgreSQL + PostGIS** — Geospatial database
- **Pydantic** — Data validation

### Infrastructure

- **Docker & Docker Compose** — Containerization
- **Google Cloud Run** — Serverless deployment
- **Vercel** — Frontend hosting (alternative)

## 🚀 Getting Started

### Prerequisites

- Node.js 18+
- Python 3.11+
- Docker & Docker Compose (recommended)
- PostgreSQL with PostGIS extension (if running without Docker)

### Quick Start with Docker

```bash
# Clone the repository
git clone https://github.com/yourusername/iran_map.git
cd iran_map

# Start all services
docker-compose up -d

# Frontend: http://localhost:3001
# Backend:  http://localhost:8000
# Database: localhost:5432
```

### Manual Setup

#### 1. Database Setup

```bash
# Using Docker for just the database
docker run -d \
  --name iran_map_db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=iran_map \
  -p 5432:5432 \
  postgis/postgis:15-3.3
```

#### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://postgres:password@localhost:5432/iran_map"

# Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 3. Frontend Setup

```bash
# From project root
npm install

# Set environment variables
export NEXT_PUBLIC_API_URL="http://localhost:8000"

# Run development server
npm run dev

# Open http://localhost:3000
```

## 📡 API Endpoints

### Events

```
GET /api/events?hours=12&verified_only=false
```

Returns protest events as GeoJSON FeatureCollection.

| Parameter       | Type | Default | Description                    |
| --------------- | ---- | ------- | ------------------------------ |
| `hours`         | int  | 12      | Time window in hours           |
| `verified_only` | bool | false   | Filter to verified events only |

### Stats

```
GET /api/stats?hours=12
```

Returns aggregate statistics.

**Response:**

```json
{
  "total_reports": 42,
  "verified_incidents": 15,
  "hours_window": 12
}
```

### Translation

```
POST /api/translate
Content-Type: application/json

{"text": "متن فارسی"}
```

Translates Persian text to English.

### Ingestion

```
POST /api/ingest
Content-Type: application/json

{"trigger_key": "your_cron_secret"}
```

Triggers ingestion from configured sources (protected by secret).

### Health Check

```
GET /health
```

Returns `{"status": "healthy"}` for load balancer checks.

## ⚙️ Environment Variables

### Frontend

| Variable              | Description     | Default         |
| --------------------- | --------------- | --------------- |
| `NEXT_PUBLIC_API_URL` | Backend API URL | `""` (relative) |

### Backend

| Variable            | Description                       | Required      |
| ------------------- | --------------------------------- | ------------- |
| `DATABASE_URL`      | PostgreSQL connection string      | Yes           |
| `CRON_SECRET`       | Secret key for ingestion endpoint | No            |
| `TELEGRAM_API_ID`   | Telegram API credentials          | For ingestion |
| `TELEGRAM_API_HASH` | Telegram API credentials          | For ingestion |

## 🐳 Docker Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Rebuild after code changes
docker-compose up -d --build

# Reset database
docker-compose down -v
docker-compose up -d
```

## 🌐 Production Deployment

### Google Cloud Run

The project includes configuration for Cloud Run deployment:

```bash
# Build and deploy
gcloud builds submit --config cloudbuild.yaml

# Or use start.sh for combined frontend + backend in single container
```

### Vercel (Frontend Only)

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel --prod
```

When deploying frontend separately, set `NEXT_PUBLIC_API_URL` to your backend URL.

## 📁 Project Structure

```
iran_map/
├── app/                    # Next.js App Router pages
│   ├── page.tsx           # Main page component
│   ├── layout.tsx         # Root layout
│   └── globals.css        # Global styles
├── components/            # React components
│   ├── Map.tsx           # deck.gl map visualization
│   └── Sidebar.tsx       # Event details panel
├── lib/                   # Shared utilities
│   └── types.ts          # TypeScript interfaces
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── main.py       # API routes
│   │   ├── models.py     # SQLAlchemy models
│   │   ├── schemas.py    # Pydantic schemas
│   │   ├── database.py   # Database connection
│   │   └── services/
│   │       └── ingestion.py  # Data ingestion
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml    # Local development setup
├── Dockerfile           # Production multi-stage build
├── start.sh             # Cloud Run startup script
└── vercel.json          # Vercel configuration
```

## 🤝 Contributing

We welcome contributions from developers, designers, translators, and human rights advocates! This project relies on community involvement to improve coverage and accuracy.

### Ways to Contribute

| Type                      | Description                                        |
| ------------------------- | -------------------------------------------------- |
| 🐛 **Bug Reports**        | Found a bug? Open an issue with steps to reproduce |
| ✨ **Feature Requests**   | Have an idea? Open an issue to discuss it first    |
| 🔧 **Code Contributions** | Submit PRs for bug fixes or approved features      |
| 🌍 **Translations**       | Help translate the UI or improve Persian geocoding |
| 📊 **Data Sources**       | Suggest reliable Telegram channels or news sources |
| 📝 **Documentation**      | Improve docs, fix typos, add examples              |

### Development Workflow

1. **Fork & Clone**

```bash
git clone https://github.com/nklsings/iran_map.git
cd iran_map
git remote add upstream https://github.com/ORIGINAL_OWNER/iran_map.git
```

2. **Create a Branch**

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

3. **Make Changes**

   - Follow the existing code style
   - Add tests for new functionality
   - Update documentation as needed

4. **Test Locally**

```bash
# Run frontend
npm run dev

# Run backend
cd backend && uvicorn app.main:app --reload

# Or use Docker
docker-compose up -d
```

5. **Commit with Conventional Commits**

```bash
git commit -m "feat: add new geocoding provider"
git commit -m "fix: resolve translation timeout issue"
git commit -m "docs: update API endpoint documentation"
```

6. **Push & Create PR**

```bash
git push origin feature/your-feature-name
```

Then open a Pull Request against `main` with a clear description.

### Code Style Guidelines

**Frontend (TypeScript/React)**

- Use functional components with hooks
- Follow existing Tailwind CSS patterns
- Use TypeScript strict mode
- Prefer named exports

**Backend (Python)**

- Follow PEP 8 style guide
- Use type hints for all functions
- Keep functions focused and small
- Document complex logic with comments

### Pull Request Checklist

- [ ] Code follows project style guidelines
- [ ] Self-reviewed the changes
- [ ] Added/updated tests if applicable
- [ ] Updated documentation if needed
- [ ] No console.log or print statements left behind
- [ ] Tested on both frontend and backend if relevant

## 🐛 Reporting Issues

### Bug Reports

When reporting bugs, please include:

- **Environment**: OS, browser, Node.js/Python version
- **Steps to reproduce**: Clear step-by-step instructions
- **Expected behavior**: What should happen
- **Actual behavior**: What actually happens
- **Screenshots/logs**: If applicable

### Feature Requests

For new features, please describe:

- **Use case**: Why is this feature needed?
- **Proposed solution**: How should it work?
- **Alternatives considered**: Other approaches you've thought about

## 🛡️ Code of Conduct

We are committed to providing a welcoming and safe environment for all contributors.

### Our Standards

**✅ Expected Behavior:**

- Be respectful and inclusive
- Welcome newcomers and help them get started
- Accept constructive criticism gracefully
- Focus on what's best for the community and project

**❌ Unacceptable Behavior:**

- Harassment, discrimination, or personal attacks
- Trolling or inflammatory comments
- Publishing others' private information
- Any conduct inappropriate in a professional setting

### Enforcement

Violations may result in temporary or permanent bans from the project. Report issues to the maintainers via GitHub issues or direct message.

## 🔒 Security

### Reporting Vulnerabilities

If you discover a security vulnerability, please **do not** open a public issue. Instead:

1. Email the maintainers directly (check GitHub profiles for contact info)
2. Include a detailed description of the vulnerability
3. Allow reasonable time for a fix before public disclosure

We take security seriously and will respond promptly to valid reports.

### Security Best Practices

- Never commit API keys, passwords, or secrets
- Use environment variables for sensitive configuration
- Keep dependencies updated
- Report any suspicious data in the ingestion pipeline

## 💬 Community

### Getting Help

- **GitHub Issues** — For bugs and feature requests
- **GitHub Discussions** — For questions and general discussion
- **Pull Request Comments** — For code-specific feedback

### Stay Updated

- ⭐ Star the repository to show support
- 👁️ Watch for release notifications
- 🍴 Fork to experiment with your own ideas

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 🙏 Acknowledgments

- [deck.gl](https://deck.gl/) — Powerful WebGL visualization
- [MapLibre](https://maplibre.org/) — Open-source mapping
- [FastAPI](https://fastapi.tiangolo.com/) — Modern Python API framework
- [PostGIS](https://postgis.net/) — Geospatial database extensions
- All contributors and the open-source community

---

<p align="center">
  <strong>Built with ❤️ for transparency and human rights documentation</strong>
</p>

<p align="center">
  <a href="#-iran-protest-map">Back to Top ↑</a>
</p>
