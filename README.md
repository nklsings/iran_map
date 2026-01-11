# 🗺️ Iran Protest Map

A real-time interactive heatmap visualization of protest events in Iran, aggregating data from multiple sources including Telegram channels and RSS feeds. Built with Next.js, FastAPI, and deck.gl.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Next.js](https://img.shields.io/badge/Next.js-16-black)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688)
![PostGIS](https://img.shields.io/badge/PostGIS-15-336791)

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

## 📄 License

This project is licensed under the MIT License.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

<p align="center">
  Built with ❤️ for transparency and human rights documentation
</p>
