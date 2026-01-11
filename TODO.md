# 📋 Iran Protest Map - TODO

A roadmap of features, improvements, and tasks for the project. Contributions welcome!

---

## 🔴 High Priority

### Data Sources

- [ ] **Define & document all active sources** — Create a sources.md with reliability ratings
- [ ] **Add official X.com (Twitter) API** — Current Nitter approach is unreliable due to blocking
- [ ] **Add more Telegram channels** — Research and add verified protest-reporting channels
- [ ] **Add Instagram scraping** — Many reports come via Instagram stories/posts
- [ ] **Add YouTube live news** — Monitor Persian news channels for breaking events
- [ ] **Add Reddit r/iran monitoring** — Community reports and discussions
- [ ] **Implement source health monitoring** — Track which sources are working/failing

### Backend Core

- [ ] **Add proper authentication** — Replace simple `trigger_key` with JWT/OAuth
- [ ] **Implement rate limiting** — Prevent API abuse
- [ ] **Add database migrations** — Set up Alembic for schema versioning
- [ ] **Improve deduplication** — Use content hashing, not just title matching
- [ ] **Add event clustering** — Group nearby events by location/time

---

## 🟡 Medium Priority

### Frontend Features

- [ ] **Add date range filter** — Allow users to view specific time periods
- [ ] **Add city/region filter** — Filter events by geographic area
- [ ] **Add search functionality** — Search events by keyword
- [ ] **Add timeline view** — Chronological event timeline sidebar
- [ ] **Add event clustering on map** — Cluster dense areas for performance
- [ ] **Add export functionality** — Export events as CSV/JSON/GeoJSON
- [ ] **Add bookmark/save events** — Let users save important events locally
- [ ] **Add notification system** — Alert users to major events (optional)

### Backend Features

- [ ] **Add caching layer** — Redis/in-memory caching for API responses
- [ ] **Add event verification workflow** — Manual verification queue for admins
- [ ] **Add intensity scoring improvements** — ML-based intensity classification
- [ ] **Add scheduled ingestion** — Cloud Scheduler / cron for automatic updates
- [ ] **Add webhooks** — Notify external services of new events
- [ ] **Add event categories** — Categorize events (protest, strike, clash, etc.)

### Geocoding Improvements

- [ ] **Add more Iranian cities** — Expand IRAN_CITIES dictionary (currently ~50)
- [ ] **Add neighborhoods/districts** — Sub-city level geocoding for Tehran, etc.
- [ ] **Add reverse geocoding API** — Convert coordinates to location names
- [ ] **Improve Persian NER** — Better named entity recognition for locations
- [ ] **Add confidence scores** — Track geocoding accuracy per event

---

## 🟢 Nice to Have

### UI/UX Enhancements

- [ ] **Add dark/light mode toggle** — Currently dark only
- [ ] **Improve mobile responsiveness** — Better touch interactions on map
- [ ] **Add PWA support** — Installable app with offline capabilities
- [ ] **Add keyboard shortcuts** — Navigate map and events via keyboard
- [ ] **Add accessibility improvements** — Screen reader support, ARIA labels
- [ ] **Add animations** — Smooth transitions for sidebar, map movements
- [ ] **Add multi-language support** — Persian, English, and other languages

### Analytics & Insights

- [ ] **Add analytics dashboard** — Charts showing trends over time
- [ ] **Add heat zones** — Historical protest hotspot analysis
- [ ] **Add sentiment analysis** — Track sentiment from report text
- [ ] **Add daily/weekly summaries** — Auto-generated reports

### DevOps & Infrastructure

- [ ] **Add GitHub Actions CI/CD** — Automated testing and deployment
- [ ] **Add automated tests** — Unit tests for backend, E2E for frontend
- [ ] **Add monitoring/alerting** — Uptime monitoring, error tracking (Sentry)
- [ ] **Add database backups** — Automated PostgreSQL backups
- [ ] **Add staging environment** — Separate staging deployment
- [ ] **Add performance monitoring** — Track API response times
- [ ] **Add load testing** — Ensure system handles traffic spikes

### Documentation

- [ ] **Add API docs page** — Interactive Swagger/OpenAPI documentation
- [ ] **Add architecture diagrams** — Detailed system diagrams
- [ ] **Add data model documentation** — Explain database schema
- [ ] **Add deployment guides** — Step-by-step for AWS, Azure, etc.
- [ ] **Create video walkthrough** — Demo video for README

---

## 🔵 Research & Exploration

### New Features to Explore

- [ ] **Real-time updates** — WebSocket for live event streaming
- [ ] **AI-powered verification** — Use LLMs to cross-reference reports
- [ ] **Image/video analysis** — Detect protests in media using CV
- [ ] **Crowdsourced reports** — Allow public submissions (with moderation)
- [ ] **Historical archive** — Long-term storage and visualization
- [ ] **Mobile app** — React Native companion app
- [ ] **Telegram bot** — Bot for event notifications

### Data Quality

- [ ] **Add source reliability tracking** — Track accuracy over time
- [ ] **Add duplicate detection ML** — ML-based near-duplicate detection
- [ ] **Add false positive filtering** — Reduce noise from unrelated content
- [ ] **Add media verification** — Check if images/videos are authentic

---

## 🛠️ Technical Debt

- [ ] **Refactor ingestion service** — Split into smaller, testable modules
- [ ] **Add TypeScript strict mode** — Enable stricter type checking
- [ ] **Standardize error handling** — Consistent error responses across API
- [ ] **Add request validation** — Pydantic validation for all endpoints
- [ ] **Clean up unused code** — Remove commented/dead code
- [ ] **Add logging** — Structured logging for debugging
- [ ] **Optimize database queries** — Add indexes, optimize joins

---

## 📊 Current Source Status

| Source | Status | Notes |
|--------|--------|-------|
| BBC Persian RSS | ✅ Working | High reliability |
| DW Persian RSS | ✅ Working | High reliability |
| VOA Persian RSS | ⚠️ Intermittent | Check feed URL |
| Reuters RSS | ✅ Working | General Middle East |
| Al Jazeera RSS | ✅ Working | Lower Iran-specific coverage |
| HRW RSS | ✅ Working | Human rights focus |
| Amnesty RSS | ✅ Working | Human rights focus |
| Twitter/Nitter | ❌ Unreliable | Nitter instances frequently blocked |
| Telegram Public | ⚠️ Partial | Some channels work, others blocked |

---

## 🎯 Milestones

### v1.0 - MVP ✅
- [x] Basic map visualization
- [x] Event ingestion from RSS
- [x] Telegram integration
- [x] Event details sidebar
- [x] Translation feature
- [x] Docker deployment

### v1.1 - Stability
- [ ] Add proper authentication
- [ ] Improve source reliability
- [ ] Add caching
- [ ] Add scheduled ingestion

### v1.2 - Features
- [ ] Add filtering (date, location)
- [ ] Add search
- [ ] Add export
- [ ] Add event categories

### v2.0 - Scale
- [ ] Real-time updates
- [ ] Mobile app
- [ ] Advanced analytics
- [ ] Crowdsourced reports

---

## 💡 Contributing

Pick any item and:

1. Comment on/create a GitHub issue
2. Fork the repo
3. Implement the feature
4. Submit a PR

See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for details.

---

## 📝 Notes

- Items marked with ❌ are blocked or have issues
- Items marked with ⚠️ need investigation
- Priority levels may change based on community feedback
- Feel free to suggest new items via GitHub Issues!

