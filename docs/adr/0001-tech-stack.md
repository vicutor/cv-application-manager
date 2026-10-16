# ADR 0001: Tech stack and architecture for the CV Application Manager

- Status: accepted
- Date: 2026-09-01

## Context

We are building a local-first, single-user application that ingests job postings,
generates postings-tailored CVs through an LLM + LaTeX pipeline, and tracks manual
application status. Full requirements live in `docs/spec/CV_APPLICATION_MANAGER_SPEC.md`.
Key constraints from the spec:

- Local-first: profile, postings, generated CVs and application history stay on disk.
- Single user, no auth, SQLite for MVP, must be able to move to PostgreSQL later
  without a model rewrite.
- Candidate profile is the source of truth, stored as YAML with stable per-fact IDs.
- The `.tex` document is generated directly (no Jinja or other template layer between
  the CV pipeline and LaTeX); it is compiled to PDF with XeLaTeX (LuaLaTeX acceptable
  alternative).
- Modular monolith, not microservices. Explicit service interfaces between modules,
  not business logic embedded in FastAPI route handlers.
- Long-running generation work (LLM calls + LaTeX compile) must not block the HTTP
  request; needs a background worker with pollable status, replaceable later with
  Redis/RQ/Celery without changing the API surface.

## Decision

### Backend

- **Python 3.12** (installed via Homebrew `python@3.12`; the system Python is 3.9 and
  is not used for this project).
- **FastAPI** for the HTTP API, **Pydantic 2.x** for request/response and structured
  LLM-output validation.
- **SQLAlchemy 2.x** (declarative, typed) as the ORM, **Alembic** for migrations.
  SQLite for MVP (`data/app.db`); models avoid SQLite-only column types so a later
  swap to PostgreSQL only touches the connection string and migration dialect.
- **httpx** for plain HTTP fetching of job posting pages; **Playwright** reserved as an
  explicit fallback for JS-rendered pages (not used in the MVP vertical slice).
- **selectolax** (or BeautifulSoup, decided at extraction-implementation time) for DOM
  cleaning.
- **PyYAML** (or ruamel.yaml if round-trip comment preservation is needed for the
  profile editor) for the candidate profile.
- A thin provider abstraction over LLM calls (own module under `services/cv_generation`),
  not a hardcoded SDK call, so OpenAI / Anthropic / OpenAI-compatible endpoints are
  swappable per pipeline stage via config. Not wired to a real provider until the
  vertical slice (paste-text import -> mock CV pipeline -> PDF -> manual applied status)
  works end-to-end with a mocked pipeline.
- Background jobs for CV generation run via a local in-process worker (simple queue +
  status polling) behind an interface that could later be swapped for Redis/RQ/Celery.

### Frontend

- **React + TypeScript + Vite**, **TanStack Query** for server state, **React Router**
  for navigation. No heavy UI framework; a small local design system is built as
  needed.
- PDF preview via the browser's native `<embed>`/`<object>` viewer to start; PDF.js is
  an option if native rendering proves insufficient.

### Document generation

- CV content is built as a structured intermediate model first (not LaTeX directly),
  then a dedicated Python module renders that structure into a complete `.tex` document
  by direct string construction — explicitly no Jinja or other template engine in this
  path, per the spec's non-negotiable constraint.
- Compilation runs XeLaTeX as a subprocess: isolated working directory per generation,
  timeout, no shell-escape, size-limited output, and a whitelist/denylist check on the
  generated LaTeX source before compiling (reject `\write18`, arbitrary `\input`, etc.).
- `pdftotext` verifies the output PDF contains selectable text; `pdfinfo` verifies page
  count against the configured limit. Both come from `poppler` (Homebrew).

### Running

- **Docker Compose** (`docker compose up`) is the primary, documented way to run the
  app — one command from a fresh clone, per the spec's recommended standard run
  method. Both services bind-mount their source directory for hot reload (backend via
  `uvicorn --reload` + an editable pip install so a bind mount over the install path
  doesn't shadow it; frontend via Vite, with `node_modules` kept in a named volume so
  the bind mount doesn't hide the image's installed packages). The backend image
  installs `texlive-xetex` + `texlive-latex-recommended` + `texlive-fonts-recommended`
  (the latter needed by `hyperref`'s internal symbol-font dependency, not obvious
  until it broke a container-only compile) and `poppler-utils`.
- Local processes (Python venv + `npm run dev`, see README) remain supported and are
  faster for running the backend test suite directly.
- `./data` is the single persistent directory for the SQLite DB, the profile YAML and
  its versions, and all per-job generation artifacts (`.tex`, `.pdf`, structured JSON,
  compile logs). Never committed; ignored via `.gitignore`. Bind-mounted into the
  backend container so state survives `docker compose down`/`up`.

### Fonts

- The CV template's font is a **bundled DejaVu Sans** (`backend/app/services/latex/
  assets/fonts/`, SIL/Bitstream-licensed TTFs checked into the repo), referenced by
  absolute filesystem path in the generated `.tex` rather than by name via
  `\setmainfont{Name}`. An OS-resolved font name is not portable: an earlier version
  used `\setmainfont{Helvetica}`, which macOS's native XeTeX font backend resolves but
  which does not exist inside the Linux container at all, and would have made every
  containerized CV generation fail. Bundling avoids depending on OS font discovery
  (fontconfig on Linux, a different backend on macOS) entirely, so generation behaves
  identically everywhere, including Polish diacritics (DejaVu has broad Unicode
  coverage).

## Consequences

- The non-Docker local setup still needs the two toolchains kept in sync (Python 3.12
  venv, Node); Docker Compose sidesteps this for anyone who just wants to run the app.
- BasicTeX is a smaller footprint than full MacTeX (~100MB vs ~6GB) for local (non-
  Docker) use but is missing packages the Docker image installs directly via apt
  (`texlive-latex-recommended`, `texlive-fonts-recommended`); local BasicTeX users may
  need `sudo tlmgr install texlive-latex-recommended` for parity.
- No LLM provider is wired up until the mocked vertical slice (paste-text -> list/detail
  -> mock CV pipeline -> PDF -> manual "applied") is verified end-to-end, per the spec's
  explicit staged rollout (`Etap 0-3` before `Etap 6` real sources / real LLM). Real URL
  import (JSON-LD extraction, SSRF-safe fetch) is done; the CV *content* pipeline
  (analysis/matching/drafting/fact-check) is still deterministic/no-LLM.
- Because business logic lives in `app/services/*` behind explicit interfaces rather
  than in route handlers, swapping SQLite -> PostgreSQL, or the in-process worker ->
  Celery/RQ, should not require changes to `app/api/*`.
