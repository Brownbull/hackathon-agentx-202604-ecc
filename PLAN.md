# Project Plan — SRE Triage Agent (ECC Workflow)

> AgentX Hackathon, April 7-9, 2026  
> Workflow: ECC (Everything Claude Code)  
> Original plan: [docs/neo-analysis/04-execution-plan.md](docs/neo-analysis/04-execution-plan.md)

---

## Phase Status

| Phase | Scope | Priority | Status | Commit | Tests |
|-------|-------|----------|--------|--------|-------|
| **1. Scaffold** | Docker, FastAPI, SQLAlchemy, Alembic, CI | MUST | ✅ Done | `36e6e75` | — |
| **2. Incident UI** | Form, list, detail pages, file uploads, HTMX | MUST | ✅ Done | `60858d8` | 14 |
| **3. Triage Agent** | Claude Haiku tool_use, codebase indexer | MUST | ✅ Done | `4ec2c31` | 15 |
| **4. Context Loader** | Solidus repo scan, keyword index, file search | MUST | ✅ Done | *(merged into Phase 3)* | — |
| **5. Ticket Service** | Auto-create ticket after triage, labels, assignee | MUST | ✅ Done | `8c487ee` | 3 |
| **6. Notifications** | Email + chat mock dispatch, on-call roster | MUST | ✅ Done | `8c487ee` | 3 |
| **7. Guardrails** | Injection detection, PII scan, rate limiting | SHOULD | ✅ Done | `814c885` | 18 |
| **8. Observability** | OpenTelemetry spans, Langfuse LLM tracing | SHOULD | ✅ Done | `4155547` | 4 |
| **9. Resolution** | Acknowledge/resolve lifecycle, reporter notify | SHOULD | ✅ Done | `phase9` | 8 |
| **10. Extras** | Severity reasoning, runbooks, dedup | COULD | ⏭ Skipped | — | — |
| **11. Documentation** | README, AGENTS_USE.md, SCALING.md, QUICKGUIDE.md, LICENSE | MUST | ✅ Done | `phase11` | — |
| **13. UI Polish** | Triage button fix, HTMX vendoring, favicon, auto-redirect, seed resilience, health check | SHOULD | ✅ Done | — | — |
| **14. UI Redesign** | Ops dashboard + chat view + settings (based on mockup 13) | MUST | ✅ Done | `phase14` | — |
| **15. Agent Providers** | Strategy pattern: Anthropic, LangChain, Managed Agents | MUST | ✅ Done | `phase15` | — |
| **16. Test Updates** | Pytest selectors updated for new UI | MUST | ✅ Done | `phase16` | 80 |
| **17. Knowledge Base** | Progressive disclosure L0-L3 + KnowledgeLoader | MUST | ✅ Done | `e33f7a3` | — |
| **18. TriageResult + VERIFY** | Pydantic BaseModel migration + file verification | MUST | ✅ Done | `e33f7a3` | — |
| **19. LangChain Upgrade** | structured_output + fallback chain + knowledge context | MUST | ✅ Done | `e33f7a3` | — |
| **20. Anthropic Upgrade** | Knowledge context integration for Premium engine | MUST | ✅ Done | `e33f7a3` | — |
| **21. Managed Agents** | Real Anthropic Managed Agents API (REST polling) | SHOULD | ✅ Done | `e33f7a3` | — |
| **22. PII Detection** | detect_pii + sanitize_for_output on all outputs | COULD | ✅ Done | `phase22` | — |
| **23. Store Engine + Tokens** | Persist engine name, token counts in Incident model | MUST | ✅ Done | `8fa7d50` | — |
| **24. Enrich Detail Page** | Pipeline progress, engine badge, expandable dispatch, component | MUST | ✅ Done | `8fa7d50` | — |
| **25. Explanation Layers** | General / Specialist / Non-technical views of diagnosis | SHOULD | ✅ Done | `8242dcf` | — |
| **26. Responsive Layout** | Desktop portrait/landscape + mobile (<768px) | SHOULD | ✅ Done | `8242dcf` | — |
| **27. Pipeline Tooltips** | Click pipeline dots → popup with stage details, auto-dismiss 5s | SHOULD | ✅ Done | — | — |
| **28. Realistic Seed Data** | 12 incidents: mixed lifecycles, attachments, guardrail rejections + engine selector on detail page | MUST | ✅ Done | — | 80 |
| **29. Langfuse Observability** | Trace failures + rejections, session_id/user_id, populate Sessions/Users tabs | SHOULD | ✅ Done | — | 82 |
| **30. Multi-Engine Seed** | Live triage with Premium + Experimental engines → capture → 6 new seed incidents with attachments + Langfuse traces | MUST | ✅ Done | — | 82 |
| **31. Guardrail Hardening** | SQL/XSS web attack patterns (4 patterns + 5 tests) | SHOULD | 🔲 Pending | — | — |
| **32. Provider Fallback** | Auto-retry next provider on triage error, ordered fallback chain | SHOULD | 🔲 Pending | — | — |
| **33. REQUIREMENTS.md** | Enumerated requirements with IDs, phase mapping, status checkboxes | MUST | 🔲 Pending | — | — |
| **34. VIDEO-SCRIPT-BRIEF.md** | Demo video script with timed segments, ECC differentiators, eval dimensions | MUST | 🔲 Pending | — | — |
| **35. Onboarding Tooltips** | Step-by-step hints on first visit guiding judges through the demo path | SHOULD | 🔲 Pending | — | — |
| **36. Doc Refresh** | Update AGENTS_USE.md, QUICKGUIDE.md, README.md for Phases 14-29 (LLM-judge critical) | MUST | 🔲 Pending | — | — |
| **37. Langfuse E2E** | Playwright tests: login to Langfuse, screenshot traces before/after triage | SHOULD | 🔲 Pending | — | — |
| **12. Demo Video** | 3-min YouTube walkthrough | MUST | 🔲 Pending | — | — |

**Test total: 80 pytest + 16 Playwright E2E**

---

## Current State (Apr 8, 2026)

### What works end-to-end
```
Submit incident → Guardrail scan → AI triage (Claude Haiku) → 
Auto-dispatch (ticket + email + chat) → Acknowledge → Resolve → Reporter notified
```

### What's in the app
- Linear/Modern dark UI with Outfit font, ambient blobs, glass cards
- Team icons and badges (Payments, Platform, Frontend, Infrastructure, Security, Fulfillment)
- Incident ID search bar (partial UUID lookup)
- Sticky incident header with ID, status, severity, team
- Acknowledge + Resolve lifecycle with resolution dialog
- Reporter email notification on resolution
- Expandable dispatch cards showing ticket/email/chat content
- Integration-ready notices (mock → Jira/SendGrid/Slack)
- Seed data: 12 sample incidents (dispatched, acknowledged, resolved, rejected, untriaged)
- Langfuse auto-seeded with dev account + API keys
- Guardrails: prompt injection detection, PII scan, rate limiting
- Observability: OpenTelemetry spans + Langfuse LLM tracing
- Full documentation: README, AGENTS_USE.md, SCALING.md, QUICKGUIDE.md, LICENSE

### What's remaining
- **Phase 12**: Demo video recording (last step)

---

## Phase 9: Resolution Tracker (Done)

**Goal**: Close the incident lifecycle — acknowledge → resolve → notify reporter.

### Delivered
- [x] POST /api/incidents/{id}/acknowledge — moves ticket to in_progress
- [x] POST /api/incidents/{id}/resolve — resolves incident, closes ticket, notifies reporter
- [x] Resolve dialog with resolution type (fix, workaround, not-a-bug, duplicate, won't fix) + notes
- [x] Reporter email notification on resolution (mock)
- [x] Lifecycle buttons in sticky header (Acknowledge, Resolve)
- [x] 8 new tests including full lifecycle test (submit → triage → acknowledge → resolve)

---

## Phase 11: Documentation (Done)

### Deliverables
- [x] README.md — solution intro, quickstart, credentials, architecture
- [x] AGENTS_USE.md — agent docs (9 sections per Anthropic template)
- [x] SCALING.md — 3-tier scaling strategy with diagrams and cost estimates
- [x] QUICKGUIDE.md — juror walkthrough (setup → full demo in 3 minutes)
- [x] LICENSE — MIT

---

## Phase 12: Demo Video (Pending)

### Script
1. Show the app (incidents list with seed data)
2. Submit a new incident through the form
3. Run AI triage — show Claude analyzing against Solidus
4. Show triage results (severity, root cause, related files)
5. Show dispatch (ticket, email, chat notifications)
6. Show Langfuse dashboard with LLM trace
7. Show guardrails (try injection → blocked)
8. Close — architecture overview, what's next

---

## Phase 13: UI Polish (Done)

### Delivered
- [x] Triage button — replaced broken HTMX (JSON swap) with JS fetch + spinner + reload
- [x] Removed orphaned reporter_team dropdown from submit form
- [x] Vendored HTMX to static/htmx.min.js (no CDN dependency)
- [x] Inline SVG favicon (no 404 in DevTools)
- [x] Submit form auto-redirects to incident detail after 1s
- [x] Root `/` redirects to `/incidents`
- [x] Seed data resilience — re-seeds on page visit if DB empty (survives test cleanup)
- [x] Health endpoint checks PostgreSQL connectivity (`ok`/`degraded`)
- [x] Updated PLAN.md with accurate test counts and state

---

## Phase 14: UI Redesign (Pending)

**Goal**: Replace the current top-nav stacked-card UI with a sidebar-based ops dashboard with 3 switchable views, matching [mockup 13](docs/mockups/13-combined-final/mockup.html).

### Architecture Decisions

- **Template strategy**: New `base_dashboard.html` + separate view partials. Old `base.html` kept as fallback.
- **Chat view**: Server-side reconstruction of incident lifecycle into message bubbles. No new models — purely presentational.
- **Sidebar navigation**: Full page loads initially. HTMX partial rendering only for triage polling.
- **Settings**: Theme/font size/font family stored in localStorage, applied via CSS classes/variables.
- **CSS**: New `dashboard.css` alongside (not replacing) old `style.css`.

### New files
- [x] `static/dashboard.css` — all dashboard styles extracted from mockup
- [x] `static/dashboard.js` — settings persistence, acknowledge/resolve/triage JS
- [x] `templates/base_dashboard.html` — sidebar + topbar + content + statusbar shell
- [x] `templates/incidents/dashboard_list.html` — incidents table view
- [x] `templates/incidents/dashboard_detail.html` — KPI strip + compact panels
- [x] `templates/incidents/dashboard_chat.html` — conversation timeline view
- [x] `templates/incidents/dashboard_submit.html` — submit form (dashboard style)
- [x] `templates/incidents/dashboard_not_found.html` — 404 page (dashboard style)

### Modified files
- [x] `app/routes/pages.py` — render new templates, pass `recent_incidents` for sidebar, `?view=chat` query param

### Chat view message reconstruction
```
1. System pill:  "Incident submitted by {reporter} at {time}"
2. User bubble:  description text
3. System pill:  "Guardrail passed — injection: X%, clean"
4. System pill:  "AI triage started — Claude Haiku 4.5"
5. AI bubble:    Triage Assessment (severity, category, component, confidence, team)
6. AI bubble:    Root Cause + Related Files chips
7. AI bubble:    Recommended Actions checklist
8. System pill:  "Auto-dispatch completed"
9. AI bubble:    Dispatch cards (ticket, email, chat)
10. System pill: "Incident resolved at {time}" (if resolved)
```

### Views
| View | URL | Topbar |
|------|-----|--------|
| List | `/incidents` | "All Incidents", no tabs, no actions |
| Detail | `/incidents/{id}` | ID + badges + Detail/Chat tabs + Ack/Resolve |
| Chat | `/incidents/{id}?view=chat` | Same topbar, Chat tab active |

---

## Phase 15: Agent Providers (Pending)

**Goal**: Refactor the triage agent to support 3 provider modes via a strategy pattern.

### Provider interface
```python
class TriageProvider(Protocol):
    async def triage(
        self, description: str, codebase_context: str,
        attachment_descriptions: list[str] | None = None,
    ) -> TriageResult: ...
```

### Providers
| Provider | Env Var | API Key | Status |
|----------|---------|---------|--------|
| `anthropic` | `TRIAGE_PROVIDER=anthropic` | `ANTHROPIC_API_KEY` | Extract from current agent.py |
| `langchain` | `TRIAGE_PROVIDER=langchain` | `GOOGLE_API_KEY` or `GROQ_API_KEY` | LangChain + free LLM (Gemini/Groq) |
| `managed` | `TRIAGE_PROVIDER=managed` | None | Stub returning hardcoded TriageResult |

### New files
- [x] `app/pipeline/triage/provider.py` — Protocol + factory
- [x] `app/pipeline/triage/anthropic_provider.py` — extracted from agent.py
- [x] `app/pipeline/triage/langchain_provider.py` — LangChain + Gemini/Groq
- [x] `app/pipeline/triage/managed_provider.py` — stub/placeholder

### Modified files
- [x] `app/pipeline/triage/agent.py` — thin facade calling provider
- [x] `app/config.py` — `triage_provider`, `google_api_key`, `groq_api_key`
- [x] `pyproject.toml` — add `langchain-core`, `langchain-google-genai`, `langchain-groq`
- [x] `docker-compose.yml` — `TRIAGE_PROVIDER`, `GOOGLE_API_KEY`, `GROQ_API_KEY` env vars
- [x] `.env` — document new vars

### Migration safety
The `run_triage()` function signature stays identical. Routes and tests call `run_triage()` — they never see the provider. Existing tests mock `run_triage` and pass regardless.

---

## Phase 16: Test Updates (Pending)

**Goal**: Update pytest and Playwright tests for the new UI selectors.

### pytest
- API tests (`/api/incidents`) return JSON — **no changes needed**
- Any tests checking HTML responses update selectors to new classes
- Add provider unit tests (mock LLM calls, verify TriageResult shape)

### Playwright E2E
- Update selectors: `.incidents-table` (was `.table`), `.panel` (was `.detail-card`), sidebar nav
- Add `data-testid` attributes to key elements for stability
- Add new tests: view switching (detail ↔ chat), settings persistence, sidebar selection

---

## Phase 17: Knowledge Base + KnowledgeLoader (Pending)

**Goal**: Progressive disclosure context system — replace raw codebase dump with curated L0-L3 knowledge layers.

**Source**: Pre-built files from El Triagista sidecar at `/home/khujta/projects/khujta_agents/_bmad/custom/agents/el-triagista/el-triagista-sidecar/knowledge/`

### Architecture
```
L0 — Architecture Map (~500 tokens)     ← ALWAYS loaded at startup
L1 — Component Index (~1,500 tokens)    ← ALWAYS loaded at startup
L2 — Domain Deep-Dive (~900 tokens)     ← ON-DEMAND per triage (keyword-matched)
L3 — Source Code (variable)             ← FALLBACK to actual codebase files
```

### New files
- [ ] `app/pipeline/knowledge/` — directory with L0, L1, L2 markdown files
- [ ] `app/pipeline/knowledge/loader.py` — `KnowledgeLoader` class: startup load L0+L1, keyword-match L2, fallback L3

### Modified files
- [ ] `app/pipeline/triage/agent.py` — replace `_build_codebase_context()` with `KnowledgeLoader.get_context()`
- [ ] `app/main.py` — load `KnowledgeLoader` in lifespan, store in `app.state`

---

## Phase 18: TriageResult Migration + VERIFY Step (Pending)

**Goal**: Migrate TriageResult to Pydantic BaseModel (required for LangChain `with_structured_output()`), add file verification.

### Changes
- [ ] `app/pipeline/triage/agent.py` — TriageResult: frozen dataclass → Pydantic BaseModel, add `engine` field
- [ ] `app/pipeline/triage/agent.py` — add `verify_files()`: check each `related_files` path exists in `settings.ecommerce_repo_path`
- [ ] `app/pipeline/triage/agent.py` — call `verify_files()` post-triage in `run_triage()` before returning
- [ ] Update tests that construct `TriageResult` directly

---

## Phase 19: LangChain Upgrade — Basic Engine (Pending)

**Goal**: Upgrade the Basic (free) engine with structured output, model fallback, and knowledge context.

### Changes
- [ ] `app/pipeline/triage/langchain_provider.py` — use `with_structured_output(TriageResult)` instead of JSON parsing
- [ ] Add `.with_fallbacks()` chain: Gemini Flash → Groq Llama
- [ ] Pass KnowledgeLoader context (L0+L1+L2) instead of raw codebase string
- [ ] Handle vision (Gemini supports image content blocks)

---

## Phase 20: Anthropic Upgrade — Premium Engine (Pending)

**Goal**: Upgrade the Premium engine with progressive disclosure knowledge context.

### Changes
- [ ] `app/pipeline/triage/anthropic_provider.py` — pass KnowledgeLoader context (L0+L1+L2) instead of raw codebase
- [ ] Keep existing tool_use pattern (already working well)

---

## Phase 21: Managed Agents — Experimental Engine (Pending)

**Goal**: Replace the keyword stub with real Anthropic Managed Agents API.

### Architecture
```
1. POST /v1/sessions           → create session (agent_id + environment_id)
2. POST /v1/sessions/{sid}/events → send incident description
3. Poll GET /v1/sessions/{sid}   → wait until status == "idle" (3-5 min)
4. GET /v1/sessions/{sid}/events → extract agent.custom_tool_use (submit_triage)
```

### Changes
- [ ] `app/pipeline/triage/managed_provider.py` — replace keyword stub with REST polling
- [ ] `app/config.py` — add `managed_agent_id`, `managed_environment_id`
- [ ] `docker-compose.yml` — add `MANAGED_AGENT_ID`, `MANAGED_ENVIRONMENT_ID` env vars
- [ ] Beta header: `anthropic-beta: managed-agents-2026-04-01`
- [ ] Timeout: 5 min max, fallback to anthropic provider on failure

---

## Phase 22: PII Detection (Pending)

**Goal**: Detect PII in input (email, phone, CC, RUT), use for diagnosis, strip from all outputs.

### New files
- [ ] `app/pipeline/guardrail/pii.py` — `detect_pii()`, `sanitize_for_output()`, regex patterns

### Changes
- [ ] Call `detect_pii()` at intake in triage pipeline
- [ ] Call `sanitize_for_output()` on all TriageResult text fields before returning
- [ ] Pattern support: email, phone, credit card, Chilean RUT

---

## Dependency Graph (Phases 17-22)
```
Phase 17 (Knowledge) ──→ Phase 19 (LangChain upgrade)
       │──→ Phase 20 (Anthropic upgrade)
       └──→ Phase 21 (Managed Agents)
Phase 18 (TriageResult + VERIFY) ──→ Phase 19
Phase 22 (PII) — independent, can run anytime
```

---

## Phase 23: Store Engine + Tokens in DB (Pending)

**Goal**: Persist triage engine name and token usage so the detail page can display them.

### Current gap
`TriageResult` has `engine`, `tokens_in`, `tokens_out` but these are lost after the request — never saved to the Incident model.

### Changes
- [ ] `app/models/incident.py` — add `triage_engine` (String), `triage_tokens_in` (Integer), `triage_tokens_out` (Integer) columns
- [ ] `app/routes/incidents.py` — persist these fields after triage: `incident.triage_engine = triage_result.engine`

---

## Phase 24: Enrich Detail Page (Pending)

**Goal**: Show the full triage output on the detail page — pipeline progress, engine badge, expandable dispatch, component, token usage.

### What to add

| Element | Where | Data source |
|---------|-------|-------------|
| **Pipeline progress bar** | Top of detail, below topbar | Incident.status (5 stages: submitted → guardrail → triage → dispatch → resolved) |
| **Engine badge** | Topbar, next to status | `incident.triage_engine` |
| **Affected component** | Description panel, below text | `incident.affected_component` |
| **Token usage** | KPI strip (6th slot) or chip | `incident.triage_tokens_in/out` |
| **Confidence interpretation** | Below KPI confidence | Thresholds: ≥0.8 High (green), ≥0.5 Medium (yellow), <0.5 Low (red) |
| **Expandable ticket** | Dispatch section | `<details>` with `incident.ticket.title` + `incident.ticket.body` |
| **Expandable email** | Dispatch section | `<details>` with `notification.subject` + `notification.body` (type=email) |
| **Expandable chat** | Dispatch section | `<details>` with `notification.body` (type=chat) |

### Files
- [ ] `templates/incidents/dashboard_detail.html` — add pipeline bar, engine badge, expandable dispatch, component, tokens
- [ ] `static/dashboard.css` — pipeline progress dots, expandable cards, engine badge styles

---

## Phase 25: Explanation Layers (Pending)

**Goal**: Show 3 views of the same diagnosis adapted by audience.

### Three layers
| Layer | Audience | Content |
|-------|----------|---------|
| **General** | Any dev in company | What broke, impact, timeline (~200 tokens) |
| **Specialist** | Dev in assigned team | Files, state machines, SQL queries, actions (~800 tokens) |
| **Non-technical** | Reporter/business | Plain English status + next steps (~100 tokens) |

### Implementation
- [ ] `app/pipeline/explain.py` — `build_explanations(triage, incident)` generates 3 layers from existing fields (no extra LLM call)
- [ ] `templates/incidents/dashboard_detail.html` — tabbed or accordion view for explanation layers
- [ ] Wire into triage endpoint: call `build_explanations()` post-triage, store in incident JSON field

---

## Phase 26: Responsive Layout (Pending)

**Goal**: Detail page works on desktop (portrait + landscape) and mobile.

### Breakpoints
| Breakpoint | Layout |
|-----------|--------|
| ≥1024px (desktop landscape) | Current: sidebar 220px + content |
| 768-1023px (desktop portrait) | Sidebar collapses to 56px icons only, content fills |
| <768px (mobile) | Sidebar hidden (hamburger toggle), single column, KPI stacks 2×3 |

### Changes
- [ ] `static/dashboard.css` — media queries for sidebar collapse + mobile single-column
- [ ] `templates/base_dashboard.html` — hamburger toggle button (hidden on desktop)
- [ ] `static/dashboard.js` — sidebar toggle handler for mobile

---

## Dependency Graph (Phases 23-26)
```
Phase 23 (Store data) ──→ Phase 24 (Enrich detail page)
                     └──→ Phase 25 (Explanation layers)
Phase 26 (Responsive) — independent, can run anytime
```

---

## Phase 27: Pipeline Step Tooltips (Pending)

**Goal**: Click a pipeline dot → popup with stage description and outcome for this incident. Auto-dismiss after 5s or click X.

### Tooltip content per stage
| Stage | Description | Dynamic data |
|-------|-------------|-------------|
| Submitted | Incident received from reporter | Reporter email, timestamp |
| Guardrail | Input scanned for injection and PII | Injection score, clean/flagged |
| Triaged | AI agent analyzed against codebase | Engine used, confidence, duration |
| Dispatched | Ticket created, team notified | Team, ticket status, channels |
| Resolved | Incident closed with resolution | Resolution type, notes, timestamp |

### Files
- [ ] `templates/incidents/dashboard_detail.html` — tooltip markup per pipeline step
- [ ] `static/dashboard.css` — tooltip positioning, animation, auto-dismiss
- [ ] `static/dashboard.js` — click handler, 5s timer, close button

---

## Phase 28: Realistic Seed Data (Pending)

**Goal**: Expand seed data from 4 to 12 incidents covering all platform scenarios: multiple engines, attachments, guardrail rejections, and mixed lifecycle states.

### Seed incident matrix

| # | Scenario | Status | Engine | Attachments | Guardrail | Lifecycle |
|---|----------|--------|--------|-------------|-----------|-----------|
| 1 | Payment 502 (existing) | Dispatched | anthropic | — | Clean | — |
| 2 | Search index empty (existing) | Dispatched | anthropic | — | Clean | — |
| 3 | Admin 403 (existing) | Dispatched | anthropic | — | Clean | — |
| 4 | Variant timeout (existing) | Dispatched | anthropic | — | Clean | — |
| 5 | Checkout failure + error log | Dispatched | langchain | `.log` file | Clean | — |
| 6 | Inventory mismatch + screenshot | Dispatched | anthropic | `.png` file | Clean | — |
| 7 | Auth lockout → acknowledged | Dispatched | anthropic | — | Clean | Ticket: in_progress |
| 8 | Shipping calc → resolved (fix) | Resolved | anthropic | — | Clean | resolution_type: fix |
| 9 | Order stuck → resolved (workaround) | Resolved | langchain | — | Clean | resolution_type: workaround |
| 10 | Prompt injection attempt | Rejected | — | — | Blocked (injection: 92%) | — |
| 11 | SQL injection attempt | Rejected | — | — | Blocked (injection: 88%) | — |
| 12 | Fresh untriaged report | Submitted | — | — | Clean | For demo triage |

### Mock attachment files
- [ ] `app/services/seed_attachments/server-error.log` — mock log with stack traces
- [ ] `app/services/seed_attachments/error-screenshot.png` — 1x1 red pixel PNG

### Changes
- [ ] `app/services/seed_data.py` — expand SEED_INCIDENTS with incidents 5-12, mixed states
- [ ] Acknowledged incidents: create ticket with `status=IN_PROGRESS`
- [ ] Resolved incidents: set `resolved_at`, `resolution_type`, `resolution_notes`, notify reporter
- [ ] Rejected incidents: set `status=REJECTED`, `injection_score=0.92`, `validation_flags={passed: false}`
- [ ] Submitted incident: just the report, no triage (for live demo)

---

## Dependency Graph (Phases 27-28)
```
Phase 27 (Tooltips) — independent
Phase 28 (Seed Data) — independent
Both can run in parallel. Phase 12 (Demo) runs last.
```

---

## Phase 30: Guardrail Hardening — SQL/XSS Patterns (Pending)

**Goal**: Add unambiguous web attack patterns as a separate detection category that won't false-positive on legitimate SRE incident reports.

### New patterns

| Pattern | Regex | Weight | Rationale |
|---------|-------|--------|-----------|
| XSS script tag | `<script\b[^>]*>` | 0.95 | Never legitimate in incident text |
| SQL UNION injection | `\bUNION\s+(ALL\s+)?SELECT\b` | 0.95 | Attack signature, not diagnostic text |
| SQL DROP TABLE | `\bDROP\s+TABLE\b` | 0.95 | Destructive DDL, never in reports |
| JavaScript URI | `javascript\s*:` | 0.90 | XSS vector via URI scheme |

### Files to modify
- [ ] `app/pipeline/guardrail/checks.py` — add `WEB_ATTACK_PATTERNS` list after `INJECTION_PATTERNS`
- [ ] `app/pipeline/guardrail/checks.py` — add `check_web_attacks()` function (parallel to `check_injection()`)
- [ ] `app/pipeline/guardrail/checks.py` — update `validate_input()` to combine: `max(injection_score, web_attack_score)`
- [ ] `app/pipeline/guardrail/checks.py` — add `"web_attack_patterns_detected"` flag
- [ ] `tests/test_guardrails.py` — 4 positive tests (one per pattern) + 1 false-positive guard

### False-positive guard test
Input: `"SQL query SELECT * FROM orders is timing out; table scans detected in production"` → must PASS (not rejected). SRE reports naturally mention SQL.

---

## Phase 31: Provider Fallback on Triage Error (Pending)

**Goal**: When the configured triage provider fails, automatically try the next available provider before returning an error.

### Architecture
Fallback logic lives in `run_triage()` in `agent.py` (not the route handler). The route stays clean; providers remain unaware of each other.

### Fallback chain
```
configured provider fails → next available → next → raise original exception
```

Provider availability check:
- `anthropic`: `settings.anthropic_api_key` is non-empty
- `langchain`: `settings.google_api_key` or `settings.groq_api_key` is non-empty
- `managed`: always available (has keyword stub fallback)

### Files to modify
- [ ] `app/pipeline/triage/agent.py` — add `_provider_available(name: str) -> bool` helper
- [ ] `app/pipeline/triage/agent.py` — add `FALLBACK_ORDER` mapping each provider to its fallback sequence
- [ ] `app/pipeline/triage/agent.py` — wrap `provider.triage()` in try/except with fallback loop
- [ ] `app/pipeline/triage/agent.py` — tag `result.engine` with fallback provenance: `"langchain (fallback from anthropic)"`
- [ ] `tests/test_provider_fallback.py` — 4 tests: successful fallback, all-fail, skip unavailable, no-fallback-on-success

### Route handler
No changes. Existing error handler (lines 289-309 in `incidents.py`) remains as last resort if ALL providers fail.

---

## Phase 32: REQUIREMENTS.md (Pending)

**Goal**: Create a requirements document with enumerated IDs, phase traceability, and status checkboxes for hackathon judges.

### File to create
- [ ] `REQUIREMENTS.md` at project root

### Categories and IDs

| Category | ID Prefix | Count | Source phases |
|----------|-----------|-------|---------------|
| Incident Submission | SUB | 5 | Phase 2 |
| Guardrails | GRD | 4 | Phase 7, 30 |
| Triage Agent | TRI | 5 | Phase 3, 15, 17-21 |
| Dispatch | DSP | 3 | Phase 5-6 |
| Resolution | RES | 2 | Phase 9 |
| Observability | OBS | 3 | Phase 8, 29 |
| Documentation | DOC | 6 | Phase 11 |
| Infrastructure | INF | 3 | Phase 1 |
| Demo | DEM | 1 | Phase 12 |

### Sections
- [ ] v1 Requirements — all enumerated with `[x]` / `[ ]` status
- [ ] v2 ECC Differentiators — 3 engines, chat view, explanation layers, provider fallback, etc.
- [ ] Out of Scope — deferred items
- [ ] Traceability table — requirement ID → phase → status

### Reference
GSD format: `/home/khujta/projects/hackathon/202604-agentx/.planning/REQUIREMENTS.md`

---

## Phase 33: VIDEO-SCRIPT-BRIEF.md (Pending)

**Goal**: Create a production brief for the 3-minute demo video highlighting ECC-specific differentiators and all 6 evaluation dimensions.

### File to create
- [ ] `docs/VIDEO-SCRIPT-BRIEF.md`

### ECC differentiators to highlight
- 3 triage engines with live switching on detail page
- Self-hosted Langfuse (judges explore without cloud signup)
- Chat conversation view (timeline reconstruction)
- Explanation layers (General / Specialist / Non-technical)
- 12 seed incidents showing all lifecycle states
- Pipeline tooltips with stage details
- Provider fallback on triage error (Phase 31)
- Web attack guardrail patterns (Phase 30)

### Timed segment structure

| Time | Section | Content |
|------|---------|---------|
| 0:00-0:15 | Hook + Intro | Problem: SRE teams drowning. Solution: AI triage agent |
| 0:15-0:30 | Architecture | Pipeline diagram: submit → guardrail → triage → dispatch → resolve |
| 0:30-1:15 | Submit + Triage | Dashboard → form → engine select → progress overlay → results |
| 1:15-1:40 | Dispatch + Lifecycle | Expandable ticket/email/chat cards, acknowledge |
| 1:40-2:00 | Resolve + Notify | Resolve dialog → reporter notified → status updated |
| 2:00-2:15 | Engine Switching | Switch Premium/Basic/Experimental on same incident |
| 2:15-2:30 | Observability | Langfuse: traces, sessions, token usage |
| 2:30-2:45 | Security | Injection attempt → blocked + guardrail badge |
| 2:45-2:55 | Chat + Layers | Chat timeline view, explanation layer toggle |
| 2:55-3:00 | Close | Stack, repo, docs |

### Sections to include
- [ ] Hard requirements (English, 3min, YouTube, #AgentXHackathon)
- [ ] 5 mandatory E2E steps (submit → triage → ticket → notify → resolve)
- [ ] 6 evaluation dimensions mapped to what to show
- [ ] Timed segment structure
- [ ] Production notes (seed incident 12 reserved for live triage demo)

### Reference
GSD format: `/home/khujta/projects/hackathon/202604-agentx/docs/VIDEO-SCRIPT-BRIEF.md`

---

## Phase 34: Onboarding Tooltips (Pending)

**Goal**: Show step-by-step hint tooltips on first visit to guide judges through the app's demo path.

### Behavior
- **Trigger**: First visit after container rebuild. Uses `localStorage.getItem("onboarding_seen")` — absent = show hints.
- **Format**: Floating tooltip (1 of N) anchored to a UI element, with **Next** / **Skip** buttons.
- **Dismiss**: Clicking Skip or finishing the sequence sets `localStorage.onboarding_seen = "true"`.
- **Reset**: Clearing localStorage (or fresh browser/incognito) restarts the tour.

### Tooltip sequence (~5 steps)

| Step | Anchor element | Hint text |
|------|---------------|-----------|
| 1 | Sidebar nav | "Welcome! This sidebar lets you navigate between incidents and submit new ones." |
| 2 | Incident list table | "Here are all tracked incidents. Click any row to see triage details." |
| 3 | Submit button (sidebar or topbar) | "Start here — submit an incident to see the AI triage in action." |
| 4 | Engine selector (detail page) | "Switch between Premium, Basic, and Experimental triage engines." |
| 5 | Pipeline dots (detail page) | "Click any pipeline stage to see what happened at each step." |

Steps 1-3 show on the list page. Steps 4-5 show on the detail page (deferred until user navigates there, or shown in a second tour).

### Implementation
- [ ] `static/onboarding.js` — tooltip engine: position calculation, step state, localStorage check, Next/Skip handlers
- [ ] `static/dashboard.css` — tooltip styles: overlay highlight, arrow, step counter badge, fade animation
- [ ] `templates/base_dashboard.html` — include `onboarding.js` script tag + tooltip container div
- [ ] Add `data-onboard="step-N"` attributes to anchor elements in list and detail templates

### Design
- Tooltip: dark card with white text, subtle arrow pointing at anchor element
- Highlight: dim overlay with cutout around the anchored element (spotlight effect)
- Step counter: "1 of 5" badge in tooltip header
- Transitions: fade in/out on step change

### Files to modify
- [ ] `static/onboarding.js` — new file (~80 lines)
- [ ] `static/dashboard.css` — add ~30 lines for tooltip + overlay styles
- [ ] `templates/base_dashboard.html` — add script tag + tooltip container
- [ ] `templates/incidents/dashboard_list.html` — add `data-onboard` attributes to sidebar, table, submit button
- [ ] `templates/incidents/dashboard_detail.html` — add `data-onboard` attributes to engine selector, pipeline dots

### No backend changes. No new dependencies. Pure JS + CSS.

---

## Phase 35: Documentation Refresh (Pending)

**Goal**: Update AGENTS_USE.md, QUICKGUIDE.md, and README.md to reflect Phases 14-29 work. CRITICAL because the first screening pass is LLM-as-judge reading the repo.

### Why this matters
From mentor sessions: "The AI will score a first filter of candidates" by reading the repo. Stale docs describing a Phase 11 app when the repo contains Phase 29 features will confuse the judge and cost us points.

### AGENTS_USE.md — section-by-section updates

**§1 Agent Overview:**
- [ ] Update tech stack to include 3 engines (Claude Haiku, Gemini Flash, Claude Agent SDK)

**§2 Agents & Capabilities:**
- [ ] Triage Agent: replace single "Claude Haiku 4.5" with 3-engine table (Premium/Basic/Experimental)
- [ ] Add tools: KnowledgeLoader (L0-L3), file verification
- [ ] Add outputs: 3 explanation layers (General/Specialist/Non-technical)
- [ ] Guardrail Agent: update pattern count after Phase 30, add PII sanitization (Phase 22)

**§3 Architecture & Orchestration:**
- [ ] Update ASCII diagram: add Engine Router branching to 3 providers
- [ ] Add Knowledge Base layer (L0-L3) in triage stage
- [ ] Add VERIFY step (file existence check) and PII Sanitization step
- [ ] Update orchestration text for strategy pattern + provider fallback

**§4 Context Engineering (BIGGEST gap):**
- [ ] Complete rewrite: replace "keyword extraction, top 5 files × 80 lines" with progressive disclosure L0-L3
- [ ] Describe: L0 architecture (~500 tokens, always), L1 component index (~1500, always), L2 domain (~900, keyword-matched), L3 source code fallback
- [ ] Update token budget for knowledge loader context sizes
- [ ] Add file verification step (Phase 18)
- [ ] Add WHY rationale: "Progressive disclosure reduces tokens ~60% vs raw dump while improving quality"

**§6 Observability:**
- [ ] Add Langfuse Sessions/Users tabs (Phase 29)
- [ ] Add session_id (incident UUID) and user_id (reporter_email) correlation
- [ ] Add trace-on-failure and trace-on-rejection
- [ ] Mention 12 seed incidents generate Langfuse traces at startup

**§7 Security & Guardrails:**
- [ ] Update pattern count after Phase 30 (add SQL/XSS mention)
- [ ] Add PII sanitization on triage outputs (Phase 22)

**§9 Scope Decisions:**
- [ ] "What we cover": add 3 engines, chat view, explanation layers, dashboard, 12 seed incidents
- [ ] "What we don't cover": prune items now covered
- [ ] "What we'd add next": update for current state

**§10 Lessons Learned:**
- [ ] Add WHY rationale for: 3 engines, progressive disclosure, self-hosted Langfuse, dashboard redesign
- [ ] Add reflections on knowledge loader, provider strategy, UI redesign

### QUICKGUIDE.md updates
- [ ] "4 pre-loaded incidents" → "12 pre-loaded incidents (dispatched, acknowledged, resolved, rejected, untriaged)"
- [ ] Add engine switching instruction + Basic (free) engine path for judges
- [ ] Update prerequisites: "At least one API key" (Anthropic OR free Google Gemini)
- [ ] Update test counts to current numbers
- [ ] Add chat view and explanation layers to test flow

### README.md updates
- [ ] Seed data: 4 → 12 incidents
- [ ] Mention dashboard UI, chat view, explanation layers
- [ ] Update test counts

### Verification
- [ ] Cross-check all numbers (patterns, seeds, tests, engines) against actual codebase before writing
- [ ] No references to Phase 30/31 features unless already delivered

---

## Phase 36: Langfuse E2E Screenshots (Pending)

**Goal**: Playwright tests that log into Langfuse, screenshot the traces dashboard before and after a triage, proving observability works end-to-end. Screenshots become visual evidence for AGENTS_USE.md and the demo video.

### Credentials
- URL: `http://localhost:3100`
- Email: `admin@sre-triage.local`
- Password: `admin123`
- Auto-seeded at startup (no manual setup needed)

### Test sequence

| Test | Steps | Screenshots |
|------|-------|------------|
| **17 — Langfuse login** | Navigate to :3100, fill email/password, submit login form | `langfuse-login.png` |
| **18 — Traces before triage** | Navigate to Traces page, screenshot existing seed traces | `traces-before.png` |
| **19 — Triage + new trace** | Create incident via API, triage via API, navigate to Traces, verify new trace appears | `traces-after-triage.png` |
| **20 — Trace detail waterfall** | Click into the new trace, screenshot the span waterfall (guardrail → context → triage → dispatch) | `trace-detail-waterfall.png` |
| **21 — Sessions tab** | Navigate to Sessions tab, screenshot showing incident session_ids | `sessions-tab.png` |

### Files to create/modify
- [ ] `e2e/langfuse.spec.ts` — new spec file with 5 tests (serial, depends on Langfuse being up)
- [ ] `e2e/screenshots/17-langfuse-login/` — auto-created by snap helper
- [ ] `e2e/screenshots/18-langfuse-traces/` — before screenshots
- [ ] `e2e/screenshots/19-langfuse-after-triage/` — after screenshots
- [ ] `e2e/screenshots/20-langfuse-detail/` — waterfall screenshot
- [ ] `e2e/screenshots/21-langfuse-sessions/` — sessions tab

### Implementation notes
- Langfuse v2 UI: login form is standard email/password, Traces page at `/traces`, Sessions at `/sessions`
- Use `page.waitForSelector` generously — Langfuse dashboard loads async
- Traces may take 1-2s to flush (Langfuse client calls `flush()` after each trace)
- Add `test.setTimeout(30_000)` for Langfuse page loads
- Reuse existing `snap()` helper from `full-flow.spec.ts`
- Tests should be in a separate spec file so they can run independently

### Selector strategy
- Langfuse is a Next.js app — prefer `data-testid` if available, fall back to role/text selectors
- Login form: `input[name="email"]`, `input[name="password"]`, `button[type="submit"]`
- Traces table: look for table rows containing "incident-triage-pipeline"
- If Langfuse selectors prove too fragile, fall back to full-page screenshots with `page.waitForLoadState("networkidle")`

### No backend changes. Screenshots auto-saved to e2e/screenshots/.

---

## Dependency Graph (Phases 30-36)
```
Phase 30 (Guardrail Hardening) — independent
Phase 31 (Provider Fallback) — independent
Phase 32 (REQUIREMENTS.md) — references 30/31 scope
Phase 33 (VIDEO-SCRIPT-BRIEF.md) — references 30/31 as differentiators
Phase 34 (Onboarding Tooltips) — independent (UI only)
Phase 35 (Doc Refresh) — should run AFTER 30/31 so docs reflect final state
Phase 36 (Langfuse E2E) — independent, needs Langfuse + app running

Recommended order: 30 + 31 (parallel) → 32 + 33 + 34 (parallel) → 35 + 36 (parallel) → 12
Phase 12 (Demo) runs last after all phases complete.
```

---

## ECC Workflow Checklist

For each remaining phase:
```
1. Update PLAN.md tasks      → document what to build
2. Implement                 → write code
3. /code-review              → catch issues
4. /verify                   → full verification loop  
5. Commit + push             → ship it
6. Update PLAN.md status     → mark done
```

---

## Commit History

| Commit | Phase | Description |
|--------|-------|-------------|
| `36e6e75` | 1 | Scaffold — Docker, FastAPI, SQLAlchemy |
| `60858d8` | 2 | Incident UI — API, HTMX, file uploads |
| `4ec2c31` | 3+4 | Triage agent + codebase indexer |
| `8c487ee` | 5+6 | Ticket service + notifications |
| `e283a88` | UI | Linear/Modern design system |
| `814c885` | 7 | Guardrails — injection, PII, rate limit |
| `4155547` | 8 | Observability — OTel + Langfuse |
| `bb7c312` | 11 | README (partial) |
| `6079507` | 14+15+16 | Triagista dashboard, provider strategy, test updates |
