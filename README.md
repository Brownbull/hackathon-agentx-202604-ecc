# Triagista

AI-powered SRE Incident Intake & Triage Agent for the [AgentX Hackathon 2026](https://github.com/anthropics/agentx-hackathon).

**The problem:** When an SRE incident is reported, engineers spend 15-30 minutes manually triaging — reading descriptions, searching codebases, classifying severity, and routing to the right team. This is slow, error-prone, and pulls senior engineers away from fixing.

**Our solution:** An AI agent that takes an incident description, analyzes it against the [Solidus](https://github.com/solidusio/solidus) e-commerce codebase (~30K LOC), and produces a structured triage in ~15 seconds: severity classification (P1-P4), root cause hypothesis, affected source files, recommended actions, and auto-dispatches a ticket with team notifications.

**Three triage engines** — choose per incident:

| Engine | Model | Cost | Speed | Best for |
|--------|-------|------|-------|----------|
| **Basic** | Gemini 2.5 Flash (via LangChain) | Lowest cost | ~8s | Budget-friendly, generous free tier |
| **Premium** | Claude Haiku 4.5 (Anthropic SDK) | ~$0.005 | ~8s | Highest accuracy |
| **Experimental** | Claude Agent SDK (Managed Agents) | ~$0.02-0.05 | ~3-5 min | Autonomous codebase exploration |

All engines produce the same structured output. The Experimental engine is the most powerful — it provisions a cloud container, clones the repo, and explores files autonomously.

## Quick Start

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Add at least one API key (see "Engine Setup" below)
#    Minimum: ANTHROPIC_API_KEY for Premium engine

# 3. Start everything
docker compose up --build -d

# 4. Open the app
open http://localhost:8100
```

The app seeds itself with 4 sample incidents on first startup.

## Engine Setup

### Basic (Free — no credit card needed)

Get a free Google Gemini key at https://aistudio.google.com/apikey and set:

```env
GOOGLE_API_KEY=AIza...
```

Optional fallback — get a free Groq key at https://console.groq.com:

```env
GROQ_API_KEY=gsk_...
```

### Premium (Anthropic SDK)

Get an API key at https://console.anthropic.com/ and set:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

### Experimental (Managed Agents)

Requires Anthropic Managed Agents beta access. Create an agent and environment in the Claude Console, then set:

```env
MANAGED_AGENT_ID=agent_...
MANAGED_ENVIRONMENT_ID=env_...
```

See `docs/managed-agent-setup.md` for the agent YAML configuration. Without these IDs, the Experimental engine falls back to a keyword-based stub.

### Which engines are available?

The submit form auto-detects which engines are configured and disables unavailable options. At minimum, set `ANTHROPIC_API_KEY` for the Premium engine.

## Access Credentials

| Service | URL | Credentials |
|---------|-----|-------------|
| **App** | http://localhost:8100 | No auth required |
| **Langfuse** (LLM Observability) | http://localhost:3100 | `admin@sre-triage.local` / `admin123` |
| **API Docs** | http://localhost:8100/docs | Swagger UI |
| **Health Check** | http://localhost:8100/health | — |
| **Observability Status** | http://localhost:8100/api/observability | — |

> Langfuse account, project, and API keys are **auto-created** on first startup. No manual setup needed.

## Demo Flow (3 minutes)

1. **View seeded incidents** at `/incidents` — 2 triaged (P1, P2) + 2 untriaged
2. **Submit a new incident** via `/incidents/new` — describe an e-commerce issue
3. **Run AI Triage** — click the button on the detail page, watch Claude analyze it (~15s)
4. **See results** — severity, root cause, affected Solidus files, recommended actions
5. **Check dispatch** — expand ticket, email, and chat cards to see generated content
6. **Resolve the incident** — Acknowledge, then Resolve with type and notes
7. **Test guardrails** — submit a prompt injection, see it blocked (400 error)
8. **View Langfuse** — open http://localhost:3100 to see LLM traces with token usage

## Architecture

```
User → FastAPI + HTMX Dashboard
         ↓
    Guardrail (injection detection, PII scan, rate limiting)
         ↓
    Engine Router ─── Basic (LangChain + Gemini/Groq)
         │          ├── Premium (Anthropic SDK + Claude Haiku)
         │          └── Experimental (Managed Agents — autonomous)
         ↓
    Knowledge Base (L0 architecture → L1 components → L2 domain deep-dive)
         ↓
    VERIFY (check related files exist in codebase)
         ↓
    PII Sanitization (strip PII from outputs)
         ↓
    Dispatch (ticket + email + chat notifications)
         ↓
    Observability (OpenTelemetry spans + Langfuse LLM traces)
```

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy (async), PostgreSQL
- **Frontend**: HTMX, Jinja2, CSS (Ops dashboard with dark/light themes)
- **AI**: Anthropic Claude Haiku 4.5, Google Gemini 2.0 Flash, Groq Llama 3.3, Claude Agent SDK
- **Knowledge**: Progressive disclosure (L0-L3) codebase knowledge base
- **Observability**: OpenTelemetry, Langfuse
- **Infrastructure**: Docker Compose, Redis

## Port Map

| Service | Port |
|---------|------|
| App | 8100 |
| PostgreSQL | 5433 |
| Redis | 6380 |
| Langfuse | 3100 |

## Testing

```bash
# Unit + integration tests (80 tests, inside Docker)
docker compose exec app pytest tests/ -v

# E2E tests with screenshots (16 tests, from host, requires Playwright)
npx playwright test

# Lint
docker compose exec app ruff check app/ tests/
```

## Project Structure

```
app/
├── config.py                 # Settings (env vars)
├── main.py                   # FastAPI app + lifespan
├── database.py               # Async SQLAlchemy
├── models/                   # ORM models (incident, ticket, notification)
├── schemas/                  # Pydantic DTOs
├── routes/                   # API + HTML page routes
├── pipeline/
│   ├── guardrail/            # Injection detection, PII scan, rate limiting
│   ├── knowledge/            # Progressive disclosure L0-L3 codebase knowledge
│   ├── triage/               # 3-engine triage (Anthropic, LangChain, Managed)
│   └── dispatch/             # Ticket + notification creation
└── services/
    ├── codebase_indexer.py   # Solidus repo keyword index
    ├── observability.py      # OpenTelemetry + Langfuse setup
    ├── seed_data.py          # Sample incidents for dev
    └── seed_langfuse.py      # Auto-create Langfuse account/keys
```
