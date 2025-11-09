# Claim Graph Setup Guide

## Overview

This implementation adds a streaming claim graph feature with self-consistent derivative generation and Exa-powered fact-checking.

## API Keys Required

You'll need the following API keys:

1. **OpenAI API Key** (required)
   - Get it from: https://platform.openai.com/api-keys
   - Used for: Derivative generation and verification

2. **Exa API Key** (required for verification)
   - Get it from: https://exa.ai
   - Used for: Web search during claim verification

3. **Kalshi Credentials** (required for market sources)
   - Sign up at: https://kalshi.com
   - Used for: Finding related prediction markets

## Setup Instructions

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your API keys:
   ```bash
   OPENAI_API_KEY=sk-your-actual-key
   EXA_API_KEY=your-actual-exa-key
   KALSHI_EMAIL=your@email.com
   KALSHI_PASSWORD=your-password
   ```

3. Install dependencies (if not already done):
   ```bash
   poetry install
   ```

## Testing

Run the basic test (requires only OpenAI API key):
```bash
poetry run python test_basic.py
```

Run the full test suite (requires all API keys):
```bash
poetry run python test_claim_graph.py
```

## Running the Server

Start the FastAPI server:
```bash
poetry run uvicorn app.main:app --reload
```

## API Endpoints

### 1. Legacy Endpoint (Non-streaming)
```
POST /graph
```
Returns a complete graph in one response (original implementation).

### 2. New Streaming Endpoint
```
POST /graph/stream
```
Returns Server-Sent Events (SSE) with incremental updates:

**Events emitted:**
- `claim_generated` - New claim added
- `claim_verifying` - Claim verification started  
- `claim_verified` - Verification complete with evidence
- `sources_found` - Market sources attached
- `graph_complete` - Final graph ready

**Example using curl:**
```bash
curl -X POST http://localhost:8000/graph/stream \
  -H "Content-Type: application/json" \
  -d '{"worldview": "AI will transform healthcare by 2025"}' \
  --no-buffer
```

## Architecture

### Data Models

**ClaimNode** - A belief/hypothesis with:
- `label`: The claim text
- `status`: generated → verifying → verified
- `sources`: List of ClaimSource objects
- `similarity`: Similarity to root claim (0-1)
- `hop`: Distance from root (0 = root)

**ClaimSource** - Evidence for a claim:
- `verification`: Exa search results with confidence
- `kalshi_market`: Related prediction market

### Pipeline Flow

1. **Generate derivatives** (3-5 sets for self-consistency)
2. **Verify each claim** (parallel, using Exa search)
3. **Merge and dedupe** by confidence
4. **Attach markets** (Kalshi sources)
5. **Build edges** (similarity between claims)
6. **Stream events** to frontend

### Model Configuration

- Derivative generation: `gpt-4o-mini` @ temp 0.5 (cheap, diverse)
- Verification: `gpt-4o` @ temp 0.2 (best tool calling)
- Cost per worldview: ~$0.15-0.26

## Files Created

- `app/models.py` - Added claim-centric models
- `app/exa_client.py` - Exa API wrapper
- `app/verification.py` - Verification agent with tool calling
- `app/claim_graph.py` - Main graph builder
- `app/derivatives.py` - Updated for self-consistency
- `app/main.py` - Added `/graph/stream` endpoint
- `test_basic.py` - Basic test suite
- `test_claim_graph.py` - Full test suite

## Next Steps

1. Set up your API keys in `.env`
2. Run `poetry run python test_basic.py` to verify setup
3. Start the server with `uvicorn`
4. Test the `/graph/stream` endpoint
5. Update frontend to consume SSE events


