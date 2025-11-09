# Worldview → Kalshi Event Graph (Python API + Next.js Web)

This repo turns a single-sentence worldview into a layered event graph of Kalshi markets and produces directional suggestions.

## Stack
- Backend: Python FastAPI + Pydantic + httpx + OpenAI
- Frontend: Next.js + Tailwind + React Flow (`@xyflow/react`)

## Prereqs
- Python 3.10+
- Node.js 18+
- OpenAI API key (`OPENAI_API_KEY`)

## Server (FastAPI)
```bash
cd server
# with Poetry
poetry install
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# or with pip
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn[standard] pydantic httpx tenacity openai python-dotenv
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Environment:
- `OPENAI_API_KEY` (required)
- `EMBEDDING_MODEL` (default `text-embedding-3-large`)
- `LLM_MODEL` (default `gpt-4.1-mini`)
- `KALSHI_BASE_URL` (default `https://api.elections.kalshi.com`)

Endpoints:
- `GET /health`
- `POST /graph` body `{ worldview, k?, maxHops?, threshold?, topN? }`

## Web (Next.js)
```bash
cd web
npm install
npm run dev
```

Config:
- `NEXT_PUBLIC_API_BASE` (default `http://localhost:8000`)

The graph UI is built with React Flow. See docs: https://reactflow.dev/

## Notes
- Cosine similarity is isolated in `server/app/embeddings.py` to allow future replacement with reasoning-based similarity.
- No persistent caching for MVP. In-request memoization used for duplicate embeddings.


