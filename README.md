# 🗺️ Iran Protest Map

A real-time interactive heatmap visualization of protest events in Iran, aggregating data from multiple OSINT sources including Telegram channels, RSS feeds, ACLED conflict data, GeoConfirmed, and more. Features AI-powered situation summaries, city analytics, airspace monitoring, and internet connectivity tracking. Built with Next.js, FastAPI, and deck.gl.

Website (URL to be updated): https://iran-protest-heatmap.vercel.app/

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
- [Pages & Routes](#-pages--routes)
- [API Endpoints](#-api-endpoints)
- [Data Sources](#-data-sources)
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
- [Roadmap](#-roadmap)

---

## ✨ Features

### Core Map Features

- **Live Heatmap Visualization** — Real-time heatmap of protest events using deck.gl with intensity-based coloring
- **Event Clustering** — Smart clustering of nearby events for better performance and readability
- **Verified vs Unverified Events** — Toggle between all reports and verified-only incidents
- **Event Details** — Click any point to view full details including media, source links, and timestamps
- **Persian → English Translation** — Built-in translation for report titles and descriptions
- **Media Support** — Display images and videos from Telegram with native playback
- **Social Sharing** — Share individual reports via Web Share API or clipboard

### Intelligence & Analytics

- **AI-Powered Situation Summaries** — Hourly GPT-4 generated intelligence reports with risk assessments
- **City Analytics Dashboard** — Track event trends, hourly patterns, and activity levels by city
- **Hotspot Detection** — Automatic identification of high-activity areas
- **Trend Analysis** — Compare week-over-week activity changes

### OSINT Data Sources

- **Multi-Source Aggregation** — RSS feeds, Telegram, YouTube, ACLED, GeoConfirmed, ArcGIS
- **Real-time Telegram Feed** — Live feed with NLP analysis, urgency scoring, and sentiment detection
- **ACLED Integration** — Armed Conflict Location & Event Data for verified conflict events
- **GeoConfirmed Import** — Import geoverified events from GeoConfirmed.org

### Specialized Monitoring

- **Airspace/NOTAM Tracking** — Monitor flight restrictions and airspace events
- **Internet Connectivity** — Province-level internet availability tracking (IODA integration)
- **PPU (Police Presence Unit)** — Crowdsourced police presence reporting with crowd-verification

### Admin Features

- **Admin Panel** — Create and verify events manually
- **Source Health Monitoring** — Track which data sources are working
- **Scheduled Ingestion** — Automatic background data collection every 15 minutes

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Frontend (Next.js)                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐│
│  │   Map.tsx   │ │ Sidebar.tsx │ │   Admin     │ │   Analytics/Summary ││
│  │  (deck.gl)  │ │  (Details)  │ │   Panel     │ │    Dashboards       ││
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Backend (FastAPI)                               │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                         API Endpoints                                ││
│  │  /events  /stats  /translate  /summary  /analytics  /connectivity   ││
│  │  /airspace  /telegram  /ppu  /osint  /acled  /admin                 ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                          Services                                    ││
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────────┐││
│  │  │ Ingestion  │ │   OSINT    │ │   ACLED    │ │  Telegram Feed     │││
│  │  │  (RSS/YT)  │ │ GeoConfirm │ │  Conflict  │ │  NLP Analysis      │││
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────────────┘││
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────────┐││
│  │  │  Summary   │ │ Analytics  │ │   NOTAM    │ │   Connectivity     │││
│  │  │  (GPT-4)   │ │   Cities   │ │  Airspace  │ │   Monitoring       │││
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────────────┘││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                      Scheduled Tasks (APScheduler)                   ││
│  │   Ingestion (15min) • Summary (60min) • Telegram (10min) • Cleanup  ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         PostgreSQL + PostGIS                             │
│   protest_events • airspace_events • telegram_messages • city_statistics │
│                      situation_summaries                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

---

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
- **APScheduler** — Background task scheduling
- **OpenAI API** — GPT-4 for situation summaries

### Infrastructure

- **Docker & Docker Compose** — Containerization
- **Google Cloud Run** — Serverless deployment
- **Vercel** — Frontend hosting (alternative)

---

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

---

## 📄 Pages & Routes

| Route        | Description                                                         |
| ------------ | ------------------------------------------------------------------- |
| `/`          | Main interactive map with heatmap visualization                     |
| `/admin`     | Admin panel for creating/verifying events (requires admin key)      |
| `/analytics` | City analytics dashboard with rankings, trends, and hourly patterns |
| `/summary`   | AI-generated situation summaries with risk assessments              |

---

## 📡 API Endpoints

### Events

```
GET /api/events?hours=24&verified_only=false&event_type=protest&cluster=true
```

Returns protest events as GeoJSON FeatureCollection with clustering.

| Parameter        | Type  | Default | Description                                                     |
| ---------------- | ----- | ------- | --------------------------------------------------------------- |
| `hours`          | int   | 24      | Time window in hours                                            |
| `verified_only`  | bool  | false   | Filter to verified events only                                  |
| `event_type`     | str   | null    | Filter by type: protest, police_presence, strike, clash, arrest |
| `cluster`        | bool  | true    | Enable clustering of nearby events                              |
| `cluster_radius` | float | 2.0     | Clustering radius in km                                         |

### Stats

```
GET /api/stats?hours=12
```

Returns aggregate statistics including event type breakdown.

### Translation

```
POST /api/translate
Content-Type: application/json

{"text": "متن فارسی"}
```

### AI Situation Summary

```
GET /api/summary                    # Get current summary
GET /api/summary/history?limit=24   # Get historical summaries
POST /api/summary/generate          # Trigger new summary generation
```

### City Analytics

```
GET /api/analytics/summary              # Overall analytics
GET /api/analytics/cities?limit=30      # City rankings
GET /api/analytics/city/{city_name}     # Single city details
GET /api/analytics/hourly?days=7        # Hourly distribution
GET /api/analytics/trends?days=30       # Trend analysis
```

### Telegram Feed

```
GET /api/telegram/feed?limit=50&min_urgency=0.5   # Get feed with NLP analysis
GET /api/telegram/urgent?threshold=0.8            # High-urgency messages only
GET /api/telegram/channels                        # List monitored channels
```

### PPU (Police Presence Unit)

```
POST /api/ppu/report    # Submit crowdsourced police presence report
GET /api/ppu/active     # Get active PPU alerts
```

Reports are auto-verified when 5+ independent reports exist within 1km in 6 hours.

### Internet Connectivity

```
GET /api/connectivity               # Province-level connectivity GeoJSON
GET /api/connectivity/provinces     # All provinces with status
GET /api/connectivity/national      # National summary
```

### Airspace / NOTAMs

```
GET /api/airspace?fir=OIIX&active_only=true   # Get active restrictions
POST /api/airspace/refresh                     # Refresh NOTAM data
```

### OSINT Data

```
GET /api/osint/fetch           # Fetch from all OSINT sources
POST /api/osint/import-kml     # Import GeoConfirmed KML (admin)
GET /api/osint/arcgis          # Fetch ArcGIS feature layers
```

### ACLED Conflict Data

```
GET /api/acled/fetch?days=30   # Fetch ACLED events
GET /api/acled/status          # Check API configuration
```

### Admin Endpoints (Protected)

```
POST /api/admin/event          # Create verified event
GET /api/admin/verify/{id}     # Verify an event
DELETE /api/admin/event/{id}   # Delete an event
POST /api/ingest               # Trigger manual ingestion
```

### Health Check

```
GET /health
```

---

## 📊 Data Sources

| Source                  | Type          | Status          | Description             |
| ----------------------- | ------------- | --------------- | ----------------------- |
| BBC Persian RSS         | News          | ✅ Working      | High reliability        |
| DW Persian RSS          | News          | ✅ Working      | High reliability        |
| VOA Persian RSS         | News          | ⚠️ Intermittent | Check feed URL          |
| Human Rights Watch      | NGO           | ✅ Working      | Human rights focus      |
| Amnesty International   | NGO           | ✅ Working      | Human rights focus      |
| ACLED                   | Conflict Data | ✅ Working      | Requires API key        |
| GeoConfirmed            | OSINT         | ✅ Working      | Geoverified events      |
| ArcGIS Feature Services | OSINT         | ✅ Working      | Military/infrastructure |
| YouTube Persian         | Social        | ✅ Working      | Live news channels      |
| Telegram Channels       | Social        | ⚠️ Partial      | Rate limited            |
| Twitter/Nitter          | Social        | ❌ Unreliable   | Nitter blocked          |

---

## ⚙️ Environment Variables

### Frontend

| Variable              | Description     | Default         |
| --------------------- | --------------- | --------------- |
| `NEXT_PUBLIC_API_URL` | Backend API URL | `""` (relative) |

### Backend

| Variable                    | Description                       | Required         |
| --------------------------- | --------------------------------- | ---------------- |
| `DATABASE_URL`              | PostgreSQL connection string      | Yes              |
| `CRON_SECRET`               | Secret key for ingestion endpoint | No               |
| `ADMIN_KEY`                 | Secret key for admin endpoints    | No               |
| `OPENAI_API_KEY`            | OpenAI API key for summaries      | For AI features  |
| `ACLED_EMAIL`               | ACLED registered email            | For ACLED data   |
| `ACLED_PASSWORD`            | ACLED account password            | For ACLED data   |
| `TWITTER_BEARER_TOKEN`      | Twitter/X API v2 Bearer Token     | For Twitter feed |
| `TELEGRAM_API_ID`           | Telegram API credentials          | For Telegram     |
| `TELEGRAM_API_HASH`         | Telegram API credentials          | For Telegram     |
| `CLOUDFLARE_API_TOKEN`      | Cloudflare Radar API              | For connectivity |
| `ENABLE_AUTO_INGESTION`     | Enable scheduled ingestion        | `true`           |
| `RSS_INTERVAL_MINUTES`      | RSS feed fetch interval           | `5`              |
| `TELEGRAM_INTERVAL_MINUTES` | Telegram fetch interval           | `5`              |
| `TWITTER_INTERVAL_MINUTES`  | Twitter API fetch interval        | `30`             |
| `YOUTUBE_INTERVAL_MINUTES`  | YouTube fetch interval            | `15`             |
| `REDDIT_INTERVAL_MINUTES`   | Reddit fetch interval             | `10`             |
| `OSINT_INTERVAL_MINUTES`    | OSINT (ArcGIS) fetch interval     | `10`             |
| `REPORT_MAX_AGE_HOURS`      | Auto-delete old reports           | `168` (7 days)   |

---

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

---

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

---

## 📁 Project Structure

```
iran_map/
├── app/                         # Next.js App Router pages
│   ├── page.tsx                # Main map page
│   ├── layout.tsx              # Root layout
│   ├── globals.css             # Global styles
│   ├── admin/
│   │   └── page.tsx           # Admin panel
│   ├── analytics/
│   │   └── page.tsx           # City analytics dashboard
│   └── summary/
│       └── page.tsx           # AI situation summary
├── components/                  # React components
│   ├── Map.tsx                 # deck.gl map visualization
│   ├── Sidebar.tsx             # Event details panel
│   └── TelegramFeed.tsx        # Live Telegram feed
├── lib/                         # Shared utilities
│   └── types.ts                # TypeScript interfaces
├── backend/                     # FastAPI backend
│   ├── app/
│   │   ├── main.py            # API routes & scheduler
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── schemas.py         # Pydantic schemas
│   │   ├── database.py        # Database connection
│   │   └── services/
│   │       ├── ingestion.py   # RSS/YouTube ingestion
│   │       ├── osint.py       # GeoConfirmed, ArcGIS
│   │       ├── acled.py       # ACLED conflict data
│   │       ├── telegram_feed.py # Telegram with NLP
│   │       ├── summary.py     # AI situation summaries
│   │       ├── city_analytics.py # City statistics
│   │       ├── notam.py       # Airspace/NOTAM parsing
│   │       ├── connectivity.py # Internet monitoring
│   │       └── persian_nlp.py # Persian text analysis
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml          # Local development setup
├── Dockerfile                  # Production multi-stage build
├── start.sh                    # Cloud Run startup script
├── cloudbuild.yaml             # GCP Cloud Build config
└── vercel.json                 # Vercel configuration
```

---

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

---

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

---

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

---

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

---

## 💬 Community

### Getting Help

- **GitHub Issues** — For bugs and feature requests
- **GitHub Discussions** — For questions and general discussion
- **Pull Request Comments** — For code-specific feedback

### Stay Updated

- ⭐ Star the repository to show support
- 👁️ Watch for release notifications
- 🍴 Fork to experiment with your own ideas

---

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

---

## 🗺️ Roadmap

See our full [TODO.md](TODO.md) for the complete roadmap. Key priorities:

### Coming Soon

| Feature                      | Status      | Priority     |
| ---------------------------- | ----------- | ------------ |
| Official X.com (Twitter) API | 🔴 Planned  | High         |
| More Telegram channels       | 🔴 Planned  | High         |
| Date range filtering         | 🟡 Planned  | Medium       |
| City/region filtering        | 🟡 Planned  | Medium       |
| Event search                 | 🟡 Planned  | Medium       |
| Export (CSV/JSON)            | 🟡 Planned  | Medium       |
| GitHub Actions CI/CD         | 🟢 Planned  | Nice to have |
| PWA support                  | 🟢 Planned  | Nice to have |
| Real-time WebSocket updates  | 🔵 Research | Future       |

### Recently Completed ✅

- AI-Powered Situation Summaries (GPT-4)
- City Analytics Dashboard
- ACLED Conflict Data Integration
- GeoConfirmed OSINT Import
- Telegram Live Feed with NLP
- Internet Connectivity Monitoring
- Airspace/NOTAM Tracking
- PPU Crowdsourced Reporting
- Event Clustering
- Admin Panel

👉 **Want to contribute?** Check [TODO.md](TODO.md) and pick a task!

---

## 🙏 Acknowledgments

- [deck.gl](https://deck.gl/) — Powerful WebGL visualization
- [MapLibre](https://maplibre.org/) — Open-source mapping
- [FastAPI](https://fastapi.tiangolo.com/) — Modern Python API framework
- [PostGIS](https://postgis.net/) — Geospatial database extensions
- [ACLED](https://acleddata.com/) — Armed Conflict Location & Event Data
- [GeoConfirmed](https://geoconfirmed.org/) — Community-verified geolocation
- [IODA](https://ioda.inetintel.cc.gatech.edu/) — Internet Outage Detection
- All contributors and the open-source community

---

<p align="center">
  <strong>Built with ❤️ for transparency and human rights documentation</strong>
</p>

<p align="center">
  <a href="#-iran-protest-map">Back to Top ↑</a>
</p>
