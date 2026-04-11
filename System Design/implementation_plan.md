# Challenge #1 — AI Email Drafting Agent: Implementation Plan

## Context
IFG's deal team loses hours hand-drafting three recurring Outlook scenarios. Two of them are **proactive** (the agent should notice the moment they're needed) and one is **reactive** (the agent responds when a human forwards it an email):

1. **Proactive — Post-Meeting Thank-You.** After a call or meeting on the user's Outlook calendar ends, send a timely thank-you that acknowledges the conversation, reinforces next steps, and leaves a positive impression.
2. **Proactive — Stale RA Re-engagement.** For emails we sent to a Referral Advocate that have not received a reply within a **user-configurable window** (e.g., 7 / 14 / 30 days), draft a light, non-pushy soft nudge that feels personal, not automated.
3. **Reactive — Inbound RA Vague Request.** When an RA in HubSpot emails asking to connect without explaining why, draft a warm but strategically inquisitive qualifying response.

Because the proactive scenarios require actually reading the Outlook mailbox + calendar, **Microsoft 365 integration is now in scope for the MVP** via the LangChain Office365 toolkit (https://docs.langchain.com/oss/python/integrations/tools/office365). All drafts are written to the Outlook **Drafts** folder for human review — the agent never auto-sends.

Submission deadline is **2026-04-13 (Monday, 4:00 PM MDT)**. Existing assets: empty `agent_challenge1.py` scaffold; `.venv` containing `langchain 1.2`, `langgraph 1.1`, `pydantic 2.12`, `httpx`, `requests`. Evaluation weights: Output Quality (M&A voice), Technical Execution (clean stack), Speed & Judgment (smart scope tradeoffs), Communication (non-technical explainability).

---

## Agent Pattern: **Trigger-driven Sequential Pipeline (LangGraph) with Tool Calling**

### Why sequential over single-prompt
- **Output quality:** M&A-advisory tone is unforgiving. Bundling classification, sentiment, and drafting in one prompt lets any upstream mistake silently corrupt the draft.
- **Debuggability:** When a draft reads wrong, we need to inspect *which* step failed. A single-prompt blackbox makes iteration slow.
- **Prompt tightness:** Short, single-purpose prompts consistently outperform one sprawling prompt. Each stage tunes independently.

### Why sequential over parallel
The dependency chain is strict: drafting depends on strategy, which depends on sentiment + context, which depends on the trigger event. The only natural parallel opportunity is the **three scanners at the front of the pipeline** (they are independent — they read different Outlook resources), so *those run in parallel*. Everything downstream of the trigger router is serial because each step feeds the next.

### Why LangGraph + Office365 toolkit specifically
- **LangGraph** already installed; native fit for stateful graphs with conditional routing, retry loops, and tool nodes.
- **Office365 toolkit** (`langchain-community`) gives us Graph-backed tools out of the box: `O365SearchEmails`, `O365SearchEvents`, `O365CreateDraftMessage`, `O365SendMessage`, `O365SendEvent`. We only call the search + create-draft tools; `SendMessage` is intentionally unused (human review gate).
- **Tool calling for sentiment analysis** is wired as a first-class LangGraph tool node, but the implementation is an external call to **Medallia Text Analytics via the Beam.ai Medallia integration** ([beam.ai/integrations/medallia](https://beam.ai/integrations/medallia/)). The node submits the relevant email text as a Medallia feedback entry through Beam.ai, polls until Medallia's Text Analytics Engine scores it, and maps the returned analytics fields onto our internal `SentimentSignals` schema (polarity, warmth, urgency, hesitation, intent). Keeping the LangGraph node interface unchanged means downstream stages (Strategy, Drafter) are unaffected — only the tool's *implementation* is a Beam.ai/Medallia round-trip rather than a homegrown LLM scorer.

---

## Pipeline Architecture

```
                        ┌────────────────────────┐
                        │   Scheduler / CLI      │
                        │ (cron, manual, or one- │
                        │  shot run-now command) │
                        └───────────┬────────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 │                  │                  │          (parallel)
                 ▼                  ▼                  ▼
        ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
        │ Scanner A      │ │ Scanner B      │ │ Scanner C      │
        │ Post-Meeting   │ │ Stale RA       │ │ Inbound Vague  │
        │                │ │ Follow-up      │ │ RA Request     │
        │ tool:          │ │                │ │                │
        │ O365Search-    │ │ tools:         │ │ tool:          │
        │ Events         │ │ O365Search-    │ │ O365Search-    │
        │                │ │ Emails (Sent   │ │ Emails (Inbox, │
        │ finds meetings │ │ folder) +      │ │ unread)        │
        │ that ended in  │ │ O365Search-    │ │                │
        │ last N hours,  │ │ Emails (Inbox, │ │ filters to RA  │
        │ filters to     │ │ Replies)       │ │ senders via    │
        │ external       │ │                │ │ HubSpot mock / │
        │ attendees      │ │ flags sent-to- │ │ domain allow-  │
        │                │ │ RA mail with   │ │ list           │
        │                │ │ no reply in    │ │                │
        │                │ │ ≥ STALE_DAYS   │ │                │
        └───────┬────────┘ └───────┬────────┘ └───────┬────────┘
                │                  │                  │
                │ TriggerEvent(type=POST_MEETING | OUTBOUND_FOLLOWUP | INBOUND_VAGUE,
                │              source_email / source_event, thread_id, metadata)
                │                  │                  │
                └──────────────────┼──────────────────┘
                                   │    (each trigger fans out → one pipeline run)
                                   ▼
                    ┌──────────────────────────────┐
                    │ 1. Trigger Router            │
                    │    + Classifier (inbound     │  confirms inbound emails are
                    │     path only)               │  actually vague RA connection
                    │                              │  requests (not noise)
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ 2. Context Extractor         │  tool calls:
                    │                              │  - O365SearchEmails (thread history)
                    │                              │  - O365SearchEvents (meeting details)
                    │                              │  - (future) HubSpot RA profile
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ 3. Sentiment Analyzer        │  TOOL CALL: analyze_sentiment
                    │                              │  → POSTs text to Medallia (via
                    │                              │    Beam.ai integration), polls
                    │                              │    Text Analytics, maps result
                    │                              │  → {polarity, warmth, urgency,
                    │                              │     hesitation, intent_signals}
                    │                              │  used to shape tone downstream
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ 4. Strategy Selector         │  combines email_type + sentiment
                    │                              │  → tone, structural_template,
                    │                              │  must_include, must_avoid
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ 5. Drafter                   │  freeform: subject + body +
                    │                              │  signature block
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ 6. Critic / Refiner          │  rubric-gated; fail → loop back
                    │                              │  to Drafter once (max 1 retry)
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ 7. Draft Writer              │  TOOL CALL:
                    │                              │  O365CreateDraftMessage
                    │                              │  → writes to Outlook Drafts folder
                    │                              │  (linked to original thread where
                    │                              │  applicable — never auto-sends)
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    [Draft visible in Outlook, awaiting reviewer edit + send]
```

**State schema** (`email_agent/state.py`):
```python
class TriggerEvent(BaseModel):
    kind: Literal["POST_MEETING", "OUTBOUND_FOLLOWUP", "INBOUND_VAGUE"]
    source_ref: str                  # Outlook message_id or event_id
    raw_payload: dict                # email body / calendar event / thread
    detected_at: datetime

class SentimentSignals(BaseModel):
    polarity: Literal["positive", "neutral", "negative"]
    warmth: float                    # 0.0–1.0
    urgency: float                   # 0.0–1.0
    hesitation: float                # 0.0–1.0
    intent_signals: list[str]        # e.g. ["exploring", "busy", "price-sensitive"]

class EmailDraftState(TypedDict):
    trigger: TriggerEvent
    email_type: EmailType | None
    context: ExtractedContext | None
    sentiment: SentimentSignals | None
    strategy: DraftStrategy | None
    draft: str | None
    critique: Critique | None
    retry_count: int
    final_draft: DraftOutput | None
    outlook_draft_id: str | None     # set by Draft Writer after O365CreateDraftMessage
```

---

## Tech Stack

| Layer | Choice | Justification |
|---|---|---|
| Orchestration | **LangGraph 1.1** | Installed; native fit for trigger→pipeline→tool-call graphs |
| LLM | **Anthropic Claude (`claude-sonnet-4-6`)** | Strong tone control, best-in-class business writing |
| Tool-calling runtime | **LangChain tool bindings** via `langchain-anthropic` | Uniform tool interface for both O365 tools and the sentiment tool |
| Outlook integration | **`langchain-community` Office365 toolkit** (`O365SearchEmails`, `O365SearchEvents`, `O365CreateDraftMessage`) | Exactly the tools the spec requires; wraps the `O365` Python lib |
| O365 auth | **`O365` library** with Azure AD app registration, **delegated** OAuth flow, token cached locally (`o365_token.txt`, gitignored) | Standard path documented in the LangChain Office365 guide |
| Sentiment tool | LangChain `@tool analyze_sentiment` that calls **Beam.ai Medallia integration** → Medallia Text Analytics, then maps the response onto `SentimentSignals` (Pydantic). Falls back to a neutral profile if Medallia is unreachable or scoring exceeds `SENTIMENT_TIMEOUT_S`. | Uses Medallia's purpose-built CX text analytics rather than a homegrown LLM scorer; isolated behind the same `@tool` interface so the rest of the graph is unaffected; explicit timeout fallback keeps a third-party outage from blocking the whole pipeline |
| Schemas | Pydantic v2 | Installed |
| SDK | `anthropic` + `langchain-anthropic` + `langchain-community` + `O365` + Beam.ai client (`beam-sdk` or REST via `httpx`) | To add to venv |
| Scheduler | Python `schedule` lib for dev; cron/Task Scheduler for prod; CLI `--run-now` flag for manual/demo | Keeps MVP demoable without requiring a daemon |
| Config | `.env` via `python-dotenv` (gitignored): `ANTHROPIC_API_KEY`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_TENANT_ID`, `STALE_RA_DAYS`, `POST_MEETING_LOOKBACK_HOURS`, `RA_DOMAIN_ALLOWLIST`, `BEAM_API_KEY`, `MEDALLIA_TENANT`, `MEDALLIA_PROGRAM_ID`, `MEDALLIA_AUTH_TOKEN`, `SENTIMENT_TIMEOUT_S` (default 20), `SENTIMENT_POLL_INTERVAL_S` (default 2) | User-configurable follow-up window + Medallia/Beam credentials live here |

---

## File Structure

```
Iconic-Founders-Agent-Challenge/
├── agent_challenge1.py                 # CLI entry point — run-now / scan-only / demo modes
├── email_agent/
│   ├── __init__.py
│   ├── config.py                       # loads .env, exposes STALE_RA_DAYS etc.
│   ├── state.py                        # Pydantic + TypedDict state + TriggerEvent + SentimentSignals
│   ├── llm.py                          # Anthropic client factory with prompt caching on IFG voice guide
│   ├── prompts.py                      # All stage prompts + IFG voice guide
│   ├── graph.py                        # LangGraph StateGraph construction + conditional edges
│   ├── scanners/                       # run in parallel, emit TriggerEvents
│   │   ├── __init__.py
│   │   ├── post_meeting.py             # uses O365SearchEvents
│   │   ├── stale_followup.py           # uses O365SearchEmails (Sent + Inbox reply check)
│   │   └── inbound_vague.py            # uses O365SearchEmails (Inbox, unread, RA allowlist)
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── trigger_router.py           # unifies TriggerEvent → EmailDraftState
│   │   ├── classifier.py               # only invoked on inbound path
│   │   ├── context_extractor.py        # O365 tool calls for thread/meeting lookup
│   │   ├── sentiment.py                # invokes analyze_sentiment tool
│   │   ├── strategy.py
│   │   ├── drafter.py
│   │   ├── critic.py
│   │   └── draft_writer.py             # O365CreateDraftMessage — the only write path
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── medallia_sentiment.py       # @tool analyze_sentiment → Beam.ai → Medallia → SentimentSignals
│   │   └── o365.py                     # thin wrapper building the toolkit + shared Account
│   └── outlook_auth.py                 # one-time OAuth flow, token persistence
├── fixtures/                           # used when O365 auth isn't available (tests + demo fallback)
│   ├── inbound_vague.json
│   ├── outbound_followup.json
│   └── post_meeting.json
├── outputs/                            # submission deliverable: the 3 generated drafts
│   ├── draft_inbound_vague.md
│   ├── draft_outbound_followup.md
│   └── draft_post_meeting.md
├── System Design/
│   ├── implementation_plan.md          # this file
│   └── architecture.md                 # one-page non-technical explainer + diagram
├── .env.example                        # all config keys documented, no secrets
├── requirements.txt
└── README.md                           # setup (incl. Azure AD app reg walkthrough) + demo commands
```

**Critical files (highest iteration value):**
- `email_agent/prompts.py` — prompt quality drives output quality; most tuning time lives here
- `email_agent/nodes/drafter.py` + `critic.py` — the quality-defining pair
- `email_agent/scanners/*.py` — correctness of the triggers determines whether the right drafts get created at the right time
- `email_agent/tools/medallia_sentiment.py` — sentiment tool output schema shapes downstream strategy; also the only third-party non-Microsoft dependency on the hot path, so its timeout/fallback behavior is what protects the deadline
- `email_agent/outlook_auth.py` + `tools/o365.py` — gate the entire proactive half of the system
- `System Design/architecture.md` — scored directly against the "Communication" evaluation criterion

---

## Implementation Steps

1. **Dependencies.** `pip install anthropic langchain-anthropic langchain-community O365 python-dotenv schedule` into the existing venv, plus the Beam.ai client for the Medallia integration (`pip install beam-sdk` — substitute the actual published package name; if Beam.ai exposes only REST, fall back to using the already-installed `httpx`). Freeze `requirements.txt`.
2. **Azure AD app registration.** One-time setup (documented in README): register an app in Entra ID, add delegated permissions `Mail.ReadWrite`, `Mail.Send`, `Calendars.Read`, `User.Read`, generate client secret, capture `CLIENT_ID` / `TENANT_ID` / `CLIENT_SECRET`.
3. **Config + state** (`email_agent/config.py`, `state.py`). Define `TriggerEvent`, `SentimentSignals`, `EmailDraftState`, and load all user-configurable knobs from `.env`: `STALE_RA_DAYS` (default 10), `POST_MEETING_LOOKBACK_HOURS` (default 6), `RA_DOMAIN_ALLOWLIST`.
4. **Outlook auth** (`email_agent/outlook_auth.py`). Wrap the `O365` `Account` object with delegated OAuth flow; persist token to `o365_token.txt` (gitignored). First run prompts browser consent; subsequent runs refresh silently.
5. **O365 tool wrapper** (`email_agent/tools/o365.py`). Instantiate `O365Toolkit` from `langchain-community`, expose the individual tools (`O365SearchEmails`, `O365SearchEvents`, `O365CreateDraftMessage`) to downstream nodes.
6. **Sentiment tool** (`email_agent/tools/medallia_sentiment.py`). LangChain `@tool analyze_sentiment(text: str) -> SentimentSignals`. Implementation:
   1. Authenticate against Beam.ai using `BEAM_API_KEY`.
   2. Call the Beam.ai Medallia integration to **create a feedback entry** in `MEDALLIA_PROGRAM_ID` whose body is the email text under analysis. Tag the entry with a UUID so we can recover the result.
   3. Poll the Medallia analytics endpoint (via Beam.ai or directly with `MEDALLIA_AUTH_TOKEN`) every `SENTIMENT_POLL_INTERVAL_S` seconds, waiting for the Text Analytics Engine to attach scores.
   4. Map Medallia's analytics fields onto our `SentimentSignals` schema: Medallia sentiment polarity → `polarity`; Medallia "emotion intensity" → `warmth` (rescaled to 0.0–1.0); Medallia "urgency" topic score → `urgency`; Medallia hesitation/uncertainty topic → `hesitation`; Medallia top topics → `intent_signals`.
   5. **Fallback**: if `SENTIMENT_TIMEOUT_S` is exceeded or any Beam.ai/Medallia call raises, return a neutral `SentimentSignals` (`polarity="neutral"`, all floats `0.5`, `intent_signals=[]`) and log a `sentiment.fallback` warning so the rest of the pipeline still produces a draft.
   6. **Cleanup (optional)**: if `MEDALLIA_DELETE_AFTER_SCORE` is true, delete the temporary feedback entry so we do not pollute Medallia's program with throwaway records.

   Unit-tested against 3–5 hand-labeled snippets using a mocked Beam.ai/Medallia client. Integration-tested once against a real Medallia sandbox program.
7. **Scanners** (`email_agent/scanners/*.py`). Each returns `list[TriggerEvent]`. Run them concurrently with `asyncio.gather` (the one place parallelism is real):
   - **Post-meeting**: `O365SearchEvents` for events with `end >= now - POST_MEETING_LOOKBACK_HOURS` and `end < now`; filter to events with external attendees; dedupe against an already-drafted cache (`.agent_state/processed_events.json`).
   - **Stale follow-up**: `O365SearchEmails` on Sent folder for messages to RA domains in the last 90 days; for each, `O365SearchEmails` on Inbox looking for a reply in the same conversationId; flag if last reply older than `STALE_DAYS`; dedupe against `.agent_state/processed_stale.json`.
   - **Inbound vague**: `O365SearchEmails` on Inbox, unread, sender in RA allowlist; dedupe against `.agent_state/processed_inbound.json`. Classification happens downstream to confirm vagueness.
8. **Prompts** (`email_agent/prompts.py`). One template per node. System prompt = shared IFG voice guide (M&A advisory register, senior-but-warm, no corporate jargon, no over-eager CTAs), cached via `cache_control`.
9. **Nodes** (`email_agent/nodes/*.py`). Each is a pure `(state) -> partial state update` function:
   - **Trigger Router**: routes to classifier (inbound) or directly to context extractor (proactive paths).
   - **Classifier**: only runs on inbound; confirms `INBOUND_VAGUE` vs. rejects (not-an-RA / not-vague → drop).
   - **Context Extractor**: calls O365 tools to pull thread history, meeting invite body, related prior emails.
   - **Sentiment**: calls the `analyze_sentiment` tool on the relevant text (inbound body / meeting invite + notes / last outbound message).
   - **Strategy**: picks tone + template from `email_type × sentiment`.
   - **Drafter**: freeform subject + body + signature.
   - **Critic**: rubric-gated structured output (pass/fail + reasons).
   - **Draft Writer**: calls `O365CreateDraftMessage`; sets `outlook_draft_id` in state. For reply scenarios, creates the draft as a reply to the original thread so it shows up in context in Outlook.
10. **Graph** (`email_agent/graph.py`). `StateGraph`: trigger_router → (classifier?) → context_extractor → sentiment → strategy → drafter → critic → draft_writer → END. Conditional edge from critic: `pass` → draft_writer, `fail AND retry_count < 1` → drafter, `fail AND retry_count >= 1` → draft_writer (ship best attempt).
11. **CLI** (`agent_challenge1.py`). Modes:
    - `python agent_challenge1.py scan` — runs all three scanners once, creates drafts for every triggered event.
    - `python agent_challenge1.py scan --kind post_meeting` — single scanner.
    - `python agent_challenge1.py run --fixture fixtures/inbound_vague.json` — bypasses O365 for offline demo / grader fallback.
    - `python agent_challenge1.py --verbose` — prints intermediate state after each node.
12. **Fixtures**. Same 3 realistic JSON sample emails as before (wealth-manager cold connect, silent construction-insurance-broker follow-up, post-intro-call CEPA advisor debrief). These serve as (a) unit-test inputs, (b) offline demo fallback, (c) fodder for submission's 3 sample drafts if live O365 demo isn't feasible.
13. **Generate sample outputs.** Run pipeline against all 3 fixtures; save rendered drafts to `outputs/*.md`. Submission deliverable.
14. **Architecture doc** (`System Design/architecture.md`). One-page non-technical explainer: problem, diagram, pattern justification, stack rationale, where the M365 toolkit + sentiment tool calls fit.
15. **README.** Setup walkthrough (Azure AD app reg, `.env`, first-run consent), demo commands, list of sample outputs, troubleshooting.
16. **Loom walkthrough (~90s).** CLI `scan` run → show new drafts appearing in Outlook Drafts folder → architecture.md scroll. Required "working demo" deliverable.
17. **Stretch (only if time permits).** Streamlit dashboard: shows scanner results, pending drafts, last run timestamp, config editor for `STALE_RA_DAYS` / `POST_MEETING_LOOKBACK_HOURS` / RA domain allowlist — ticks the UI bonus.

---

## Verification

**Auth smoke test:**
- `python -m email_agent.outlook_auth` — completes OAuth, writes token, lists 3 most recent inbox subjects via `O365SearchEmails`.

**Scanner-level checks:**
- **Post-meeting**: create a test calendar event ending 10 minutes ago with an external attendee; run `scan --kind post_meeting`; confirm a thank-you draft is created in Outlook Drafts referencing the meeting title.
- **Stale follow-up**: set `STALE_RA_DAYS=1`, send a test email from a throwaway account to an RA-domain address, wait, run `scan --kind stale_followup`; confirm a soft-nudge draft is created. Re-run → should *not* double-draft (dedupe cache works).
- **Inbound vague**: send a test "would love to connect sometime" email to the Outlook inbox from an RA-allowlisted address; run `scan --kind inbound_vague`; confirm a qualifying-question draft is created as a reply to the original thread.

**Sentiment tool tests:**
- **Unit (mocked):** stub the Beam.ai client to return canned Medallia analytics payloads for 3 hand-labeled snippets (enthusiastic intro, hesitant busy exec, warm post-meeting close); assert the field-mapping produces the expected `polarity` / `warmth` / `hesitation` buckets.
- **Integration (one-shot):** with real `BEAM_API_KEY` + Medallia sandbox creds, run `python -m email_agent.tools.medallia_sentiment "Thanks for the great chat earlier — let's circle back next week."` and confirm a non-fallback `SentimentSignals` comes back inside the timeout budget.
- **Fallback test:** point `BEAM_API_KEY` at an invalid value and confirm the tool returns the neutral fallback within `SENTIMENT_TIMEOUT_S` rather than raising.

**Per-fixture functional checks (offline mode):**
- `inbound_vague.json` → draft is warm, contains ≥1 qualifying question, does **not** propose a meeting time yet, <150 words.
- `outbound_followup.json` → draft is short (<120 words), references the prior outreach, no pressure CTAs, offers an easy out.
- `post_meeting.json` → draft thanks specifically (not generically), restates ≥2 concrete next steps from the fixture, proposes a concrete follow-up window.

**Pipeline introspection:**
- `python agent_challenge1.py run --fixture fixtures/inbound_vague.json --verbose`: confirm classifier = `INBOUND_VAGUE`, sentiment = reasonable (e.g., neutral/warm), strategy tone = `warm_inquisitive`, drafter non-empty, critic pass, Draft Writer either creates O365 draft or (offline) writes to `outputs/`.

**Quality smoke test:**
- Read all 3 outputs aloud. Senior M&A advisor or ChatGPT? If the latter, iterate on `prompts.py` / voice guide — highest-leverage fix.

**Submission package check:**
- `outputs/*.md` committed ✓
- `System Design/architecture.md` + `implementation_plan.md` committed ✓
- README runs end-to-end on a fresh clone (incl. Azure AD setup) ✓
- Loom link + zip sent to `heidi.heckler@iconicfounders.com` with subject `AI Intern Assignment – [Name] – Challenge #1`

---

## What I'd Build Next (for the submission's 3–5 sentence note)
1. **HubSpot CRM node:** replace the static RA domain allowlist with a live HubSpot lookup so scanners pull real RA contacts + deal stage + last touchpoint into the context extractor.
2. **Human feedback loop:** log reviewer edits to the Outlook drafts; use them as few-shot examples in the voice guide (continuous prompt improvement without fine-tuning).
3. **Parallel tone variants:** at the drafter step, generate warm/direct/formal in parallel, let the reviewer pick in Outlook via three separate draft messages.
4. **Production scheduling:** move from `python agent_challenge1.py scan` cron to an Azure Function / Power Automate flow triggered on Graph webhook subscriptions for `messages` and `events`, so drafts appear near-instantly instead of on a poll.
5. **Tone/sentiment calibration dashboard:** show the sentiment tool's output distribution against reviewer outcomes to catch drift.
6. **Cache Medallia scores per `(sender, conversationId)`:** many drafts in this system are replies in long threads where the inbound side's sentiment does not move much between scans. Caching scored entries by conversation would cut Medallia round-trips dramatically and tighten the latency budget.

---

## Assumptions
- **LLM provider = Anthropic Claude** (not OpenAI). Swap `email_agent/llm.py` only if the team prefers OpenAI.
- **Outlook integration = delegated OAuth to the user's own Outlook account.** No shared service account for MVP.
- **Drafts never auto-send.** Every output lands in the Drafts folder for human review. `O365SendMessage` is intentionally unused.
- **RA identification = domain allowlist** in `.env` for MVP. HubSpot integration is explicitly deferred to "what I'd build next."
- **User-configurable windows** (`STALE_RA_DAYS`, `POST_MEETING_LOOKBACK_HOURS`) live in `.env` and can be overridden per-run via CLI flags.
- **UI is stretch**, not MVP. CLI + Outlook drafts folder are enough for a demoable Loom.
- **Sentiment provider = Medallia Text Analytics, accessed via the Beam.ai Medallia integration.** Requires a Beam.ai account and a Medallia program ID + auth token. The Beam.ai integration is used for the write path (creating feedback entries); the read path may go through Beam.ai or directly to Medallia depending on which surface exposes scored entries first.
- **Medallia is on the critical path of every draft.** A `SENTIMENT_TIMEOUT_S` fallback to neutral sentiment exists so a Medallia outage degrades draft quality but does not block the pipeline.
