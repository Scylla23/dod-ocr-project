# DOD OCR Project

PDF extraction tool for DoD engineering documents. FastAPI backend + React/Vite frontend. Uses LLM vision providers (Anthropic, OpenAI-compatible) to extract structured fields from rendered PDF pages.

## Stack

- **Backend** — FastAPI, PyMuPDF, Anthropic + OpenAI SDKs (`backend/`)
- **Frontend** — React 18, Vite, Zustand, react-pdf (`frontend/`)
- **Package managers** — `uv` (Python), `npm` (Node)

## Prerequisites

- Node.js 18+
- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

## Setup

From the project root:

```bash
npm install
```

Installs frontend dependencies and syncs the backend Python environment in one shot.

Create `backend/.env` with at least one provider key:

```env
ANTHROPIC_API_KEY=sk-ant-...
# or
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1   # override for openai-compatible providers
```

## Run

Start backend (`:8000`) and frontend (`:5173`) together:

```bash
npm run dev
```

Individual:

```bash
npm run dev:backend
npm run dev:frontend
```

## Test

```bash
npm test
```

Runs the frontend Vitest suite and the backend pytest suite.

## Build

```bash
npm run build
```

Produces the frontend production build under `frontend/dist/`.

## Layout

```
backend/    FastAPI app — providers, extractor, session store
frontend/   React UI — upload, PDF viewer, fields pane
docs/       Project documentation
```
