# Contributing to Iran Protest Map

First off, thank you for considering contributing to Iran Protest Map! It's people like you that help make this tool valuable for human rights documentation and transparency.

## 📑 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Style Guidelines](#style-guidelines)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the maintainers.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/nklsings/iran_map.git
   cd iran_map
   ```
3. **Add the upstream remote**:
   ```bash
   git remote add upstream https://github.com/ORIGINAL_OWNER/iran_map.git
   ```
4. **Set up the development environment** (see [Development Setup](#development-setup))

## How Can I Contribute?

### 🐛 Reporting Bugs

Before creating bug reports, please check existing issues. When creating a bug report, include as many details as possible using our bug report template.

### ✨ Suggesting Features

Feature suggestions are welcome! Please use the feature request template and be as detailed as possible.

### 📊 Suggesting Data Sources

Know a reliable source for protest information? Use the data source template to suggest it.

### 🔧 Code Contributions

1. Check the issue tracker for open issues or create a new one
2. Comment on the issue to let others know you're working on it
3. Fork, code, test, and submit a PR

### 📝 Documentation

Documentation improvements are always welcome:

- Fix typos or unclear wording
- Add examples
- Improve API documentation
- Translate documentation

### 🌍 Translations

Help translate:

- UI elements to Persian or other languages
- Improve geocoding for Persian city names
- Documentation to other languages

## Development Setup

### Prerequisites

- Node.js 18+
- Python 3.11+
- Docker & Docker Compose
- Git

### Quick Setup

```bash
# Clone and enter directory
git clone https://github.com/nklsings/iran_map.git
cd iran_map

# Start all services with Docker
docker-compose up -d

# Frontend: http://localhost:3001
# Backend: http://localhost:8000
```

### Manual Setup

**Frontend:**

```bash
npm install
npm run dev
```

**Backend:**

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Style Guidelines

### TypeScript/React (Frontend)

- Use functional components with hooks
- Use TypeScript strict mode
- Follow existing Tailwind CSS patterns
- Prefer named exports over default exports
- Use meaningful variable and function names

```typescript
// ✅ Good
export function EventCard({ event }: EventCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  // ...
}

// ❌ Avoid
export default function EC(props: any) {
  const [e, setE] = useState(false);
  // ...
}
```

### Python (Backend)

- Follow PEP 8 style guide
- Use type hints for all functions
- Use docstrings for public functions
- Keep functions focused and small

```python
# ✅ Good
def get_events_by_location(
    latitude: float,
    longitude: float,
    radius_km: float = 10.0
) -> list[ProtestEvent]:
    """Fetch events within a radius of the given coordinates."""
    # ...

# ❌ Avoid
def get(lat, lon, r=10):
    # ...
```

## Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/). Format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

| Type       | Description                                             |
| ---------- | ------------------------------------------------------- |
| `feat`     | New feature                                             |
| `fix`      | Bug fix                                                 |
| `docs`     | Documentation only                                      |
| `style`    | Formatting, no code change                              |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf`     | Performance improvement                                 |
| `test`     | Adding or updating tests                                |
| `chore`    | Maintenance tasks                                       |

### Examples

```bash
feat(map): add clustering for dense event areas
fix(api): resolve timeout on large event queries
docs(readme): add deployment instructions
refactor(ingestion): simplify geocoding logic
```

## Pull Request Process

1. **Update your fork** with the latest upstream changes:

   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Create a feature branch**:

   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes** following the style guidelines

4. **Test thoroughly**:

   - Run the frontend and backend locally
   - Test your specific changes
   - Ensure no regressions

5. **Commit your changes** using conventional commits

6. **Push to your fork**:

   ```bash
   git push origin feature/your-feature-name
   ```

7. **Open a Pull Request**:

   - Use the PR template
   - Link to related issues
   - Provide screenshots if UI changes
   - Request review from maintainers

8. **Address review feedback** promptly

9. **Celebrate** when merged! 🎉

## Questions?

Feel free to:

- Open a discussion on GitHub
- Comment on an issue
- Reach out to maintainers

Thank you for contributing! 🙏
