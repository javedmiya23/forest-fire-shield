# Contributing to Forest Fire Shield

Thank you for your interest in contributing! This project is a final-year academic demo for wildfire monitoring using IoT sensors and geospatial simulation. We welcome improvements that make it more robust, maintainable, and production-ready.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Branching Strategy](#branching-strategy)
- [Commit Message Convention](#commit-message-convention)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)

---

## Code of Conduct

By participating, you agree to uphold a respectful, inclusive, and harassment-free environment. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) (or adopt standard [Contributor Covenant](https://www.contributor-covenant.org/)).

---

## How to Contribute

1. **Fork** the repository
2. **Clone** your fork: `git clone https://github.com/<your-username>/forest-fire-shield.git`
3. **Create a branch**: `git checkout -b feat/your-feature-name`
4. **Make changes** following the standards below
5. **Test** locally
6. **Commit** with conventional messages
7. **Push** and open a **Pull Request**

---

## Development Setup

### Prerequisites

- **Python 3.11+** (backend)
- **Node.js 20+** & **npm 10+** (frontend)
- **PostgreSQL 16+** with **PostGIS 3.4+** (or use Docker)
- **Git**

### Quick Start (Docker)

```bash
# Start PostGIS + Grafana/OTel stack
cd backend
docker compose up -d

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Backend
cd ../backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (new terminal)
cd ../frontend
npm ci
npm start
# Open http://localhost:4200
```

### Without Docker

Install PostgreSQL + PostGIS locally, create database `forest_fire_shield`, update `DATABASE_URL` in `.env`.

---

## Branching Strategy

| Branch Type | Prefix | Purpose |
|-------------|--------|---------|
| Feature | `feat/` | New functionality |
| Bugfix | `fix/` | Bug fixes |
| Docs | `docs/` | Documentation only |
| Refactor | `refactor/` | Code restructuring |
| Chore | `chore/` | Tooling, deps, CI |
| Release | `release/` | Version preparation |

**Main branch**: `main` (protected, requires PR review)

---

## Commit Message Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

<body>

<footer>
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `build`, `ci`

**Examples**:
```
feat(backend): add fire spread simulation engine
fix(frontend): resolve map rendering issue on mobile
docs(readme): update installation steps for Windows
chore(deps): upgrade Angular to v21.2
```

---

## Pull Request Process

1. **Title**: Clear, conventional format: `feat(scope): description`
2. **Description**: What, why, and how. Link related issues.
3. **Checks**: All CI must pass (lint, typecheck, tests)
4. **Review**: At least 1 approval required
5. **Merge**: Squash and merge to `main`

---

## Coding Standards

### Backend (Python/FastAPI)

- **Formatter**: `ruff format` (or `black`)
- **Linter**: `ruff check` (or `flake8`)
- **Type Check**: `mypy` (strict mode)
- **Imports**: `isort` (or `ruff`)
- **Line Length**: 100 chars

```bash
# Run all checks
ruff check .
ruff format .
mypy backend/app
```

### Frontend (Angular/TypeScript)

- **Formatter**: `prettier --write`
- **Linter**: `ng lint` (ESLint)
- **Type Check**: `npx tsc --noEmit`
- **Style**: Tailwind CSS utility-first

```bash
# Run all checks
npm run lint
npx prettier --check .
npx tsc --noEmit
```

---

## Testing

### Backend
```bash
cd backend
pytest --cov=app --cov-report=term-missing
```

### Frontend
```bash
cd frontend
npm test -- --watch=false --browsers=ChromeHeadless
```

---

## Documentation

- Update `README.md` for user-facing changes
- Update `docs/` for architecture/design changes
- Add docstrings to new public functions/classes
- Keep `CHANGELOG.md` (if exists) updated

---

## Questions?

Open a [Discussion](https://github.com/javedmiya23/forest-fire-shield/discussions) or [Issue](https://github.com/javedmiya23/forest-fire-shield/issues).

---

**Happy coding!** 🌲🔥