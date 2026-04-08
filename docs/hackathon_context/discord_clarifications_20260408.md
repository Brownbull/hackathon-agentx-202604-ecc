# Discord Clarifications — 2026-04-08 Differential

New information from Discord channels captured between April 7 ~16:00 and April 8 ~16:05 UTC.
This document covers ONLY net-new clarifications not already in `discord_clarifications.md` or other `hackathon_context/` files.

---

## NEW Organizer Clarifications

### UI: Build it yourself, leverage OSS

> "You should build it. Though we recommend you to not build everything and focus on leveraging open source solutions/stacks."
> — sebastianmontagna, replying to whether the UI is pre-defined or flexible

**Impact:** Confirms UI is our responsibility. Leveraging OSS stacks (e.g., HTMX, Tailwind) is explicitly encouraged over building from scratch.

### E-commerce codebase: Running it is optional but better

> "That's a good question. I would say that is up to you to define the scope. Obviously running it is better, from an engineering perspective. Though, as we mentioned, you can mock data. So you can trigger the failures that will occur yourself."
> — sebastianmontagna

**Impact:** We do NOT need to run the e-commerce app. Reading the codebase for context analysis is sufficient. Running it is a plus but not required.

### Who is the reporter? Internal SRE stakeholders

> "The Agent/s would be a Software Reliability Engineering team asset and will report to them. It is for internal ticketing operations."
> — sebastianmontagna

> "The e-commerce client and an Internal QA/L1 Support are good examples of reporters. It can also be a report generated automatically by the infrastructure due to an external attack, malfunction, etc."
> — sebastianmontagna

**Impact:** The agent serves an internal SRE team. Reporters can be:
1. Internal QA / L1 Support
2. E-commerce end-users (reporting bugs)
3. Automated infrastructure alerts

### Focus is on ticket processing, not ticket type

> "The challenge is more focused on 'How do you handle and process the reported ticket(s) successfully', not on the specific ticket. But, if you create a workflow that handles multiple tickets intelligently and such, it is obviously better."
> — sebastianmontagna

**Impact:** Judges care about the triage quality and workflow, not about covering every possible incident type. Handling multiple tickets intelligently is a differentiator.

### Scope definition is on us

> "It is up to you to define the scope, what are you addressing, why, and how would you address others. That's why we added the AGENTS_USE.md and SCALING.md, between others, documents as part of the requirements."
> — sebastianmontagna

**Impact:** AGENTS_USE.md and SCALING.md are where we justify our scope decisions. We should explicitly state what we cover, what we don't, and why.

### Docker is mandatory, not Podman

> "They are interoperable mostly, so please use Docker so solutions are standardized."
> — sebastianmontagna

**Impact:** No change for us (already using Docker Compose).

### No API keys in repo — confirmed again

> "It should NOT include any API keys. You need to provide an .env.example file where those api keys can be configured, with clear explanations for us to use our API keys and run it."
> — sebastianmontagna

**Impact:** Already compliant. .env.example must have clear comments.

### Any e-commerce repo is allowed

> "You are open to choose yours. We just provided recommendations."
> — sebastianmontagna, confirming medusajs/medusa is acceptable

**Impact:** No change (we're using Solidus, which is in the recommended list).

---

## NEW Deadline Clarification

### Deadline is THURSDAY April 9, not Wednesday

> "The submission deadline is Thursday, April 9 at 9:00 PM Colombia time (COT, UTC-5)."
> "(The FAQ mistakenly said 'Wednesday, April 9', just fixed it)"
> — sebastianmontagna

**Impact:** Deadline confirmed as Thursday. We have ~29 hours from this export.

### Submission form coming

> "We will have a form to send the resources."
> — miguelteheran (mentor), quoting the guidelines

**Impact:** Watch #hackathon-announcements for the submission form link.

---

## NEW from Mentor Sessions

### Observability session recording available

> Learning Session: "AI Observability in Production Platforms"
> Recording available at: https://youtube.com/live/KLd9R1SUnEE

**Impact:** Good reference for our Langfuse integration approach.

### Mentor session tomorrow (April 9)

> "There will be another mentor session tomorrow."
> — sebastianmontagna

**Impact:** One more chance to ask questions before deadline.

---

## Items NOT in Previous Docs — Action Required

| # | Finding | Action for Us | Priority |
|---|---------|---------------|----------|
| 1 | Reporter can be automated infrastructure (not just humans) | Consider adding a note in AGENTS_USE.md about supporting automated alert ingestion as a future capability | Low |
| 2 | "Handle multiple tickets intelligently" is a differentiator | Our current single-ticket flow is fine for MVP, but mention multi-ticket handling in SCALING.md | Medium |
| 3 | AGENTS_USE.md + SCALING.md justify scope decisions | Make sure these docs explicitly state what we cover and what we'd add next | High |
| 4 | Submission form not yet shared | Monitor #hackathon-announcements for the link | High |
| 5 | Observability session recording available | Watch for tips on what judges expect from observability evidence | Low |

---

## No Changes To

These items from `discord_clarifications.md` remain unchanged:
- 5-step core flow (submit → triage → ticket → notify → resolve)
- AGENTS_USE.md 9-section template requirement
- Evaluation dimensions (reliability, observability, scalability, context engineering, security, documentation)
- API key guidance (use .env.example, support OpenAI/Anthropic endpoints)
- Demo video format (3 min, English, YouTube, #AgentXHackathon)
- Mocked integrations are acceptable
