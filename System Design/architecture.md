# IFG Email Drafting Agent — Architecture (one page)

## What it does

The agent watches an IFG advisor's Outlook for three specific situations and prepares a draft reply that the advisor can review, lightly edit, and send. It does **not** send anything on its own — every output lands in the Outlook Drafts folder. The three situations are:

1. **Post-meeting follow-up** — a calendar event with an external attendee just ended and no thank-you has been sent yet.
2. **Stale RA follow-up** — an outbound message to a referring advisor (wealth manager, lawyer, accountant) has gone two weeks without a reply.
3. **Vague inbound RA request** — a referring advisor has sent a generic "let's connect" email with no client context.

For each situation, the agent writes a short, voice-aligned draft that sounds like it came from a senior M&A advisor — not a chatbot.

## How it works (non-technical)

The agent is a small assembly line. Each station does one job and hands the work to the next station. There are nine stations:

| # | Station | What it does |
|---|---|---|
| 1 | **Scanners** | Three watchers — one for the calendar, one for sent mail, one for inbox — each producing a "trigger" when they spot one of the three situations. Already-processed items are remembered so nothing gets drafted twice. |
| 2 | **Trigger router** | Tags the trigger with its type and decides whether the draft needs the gatekeeper (only inbound vague does). |
| 3 | **Classifier** *(inbound vague only)* | A short LLM check: is this really a generic ask, or is there enough substance to skip the gatekeeper? Drops genuine spam. |
| 4 | **Context extractor** | Pulls the relevant facts out of the email or meeting — sender name, organization, what was discussed, what was promised, days since last touch. This is the only station that talks to Outlook. |
| 5 | **Sentiment analyzer** | Sends the relevant text to **Medallia Text Analytics** (via the Beam.ai integration) and reads back a small sentiment profile: warmth, urgency, hesitation, intent signals. If Medallia is slow or unreachable, the station returns a neutral profile and the pipeline keeps moving. |
| 6 | **Strategy planner** | An LLM call that picks the tone, the structural template, what the draft must include, and what it must avoid — given the email type, the extracted context, and the sentiment profile. |
| 7 | **Drafter** | An LLM call that writes the actual email body and subject line, following the strategy and the IFG voice guide (no "just", no "circle back", no exclamation marks, one ask per email, first-name signoff). |
| 8 | **Critic** | A second LLM call that scores the draft against a rubric: voice compliance, single-CTA discipline, specificity, word-count fit. If the draft fails, it goes back to the Drafter with the criticism — but only once, to keep latency bounded. |
| 9 | **Draft writer** | Saves the approved draft into Outlook's Drafts folder (when live) **and** writes a markdown copy under `outputs/` so the run is reviewable offline. |

## What it is **not**

- **Not autonomous.** Nothing leaves the building without the advisor pressing Send.
- **Not a chatbot.** There is no conversation loop — each trigger produces exactly one draft.
- **Not a general assistant.** It only handles the three situations above. Anything else is invisible to it.
- **Not a swarm of subagents.** It is a single workflow with named stations and fixed edges between them. The Critic↔Drafter loop is the only place that can repeat, and it caps at one retry.

## Where the risk lives

- **Voice drift.** The Critic exists specifically to catch drafts that read like a generic LLM. The voice guide is shared between the Drafter (as guardrails) and the Critic (as a rubric) so they stay in agreement.
- **Medallia outage.** Sentiment is on the critical path. The neutral fallback means a Medallia outage degrades draft *quality* but does not block the *pipeline*.
- **Outlook auth.** Microsoft Graph delegated OAuth tokens expire. The token file is refreshed automatically; first-run requires the advisor to complete a browser sign-in once.
- **Duplicate drafts.** The scanners use a small JSON dedupe cache so the same meeting or thread does not generate a second draft on the next scan.

## Where to look in the code

- `email_agent/graph.py` — the assembly line itself (LangGraph `StateGraph`).
- `email_agent/nodes/` — one file per station.
- `email_agent/scanners/` — the three Outlook watchers.
- `email_agent/tools/medallia_sentiment.py` — the Beam.ai → Medallia round-trip.
- `email_agent/prompts.py` — the IFG voice guide and every station's system prompt.
- `outputs/` — markdown copies of the three sample drafts the system produces against the included fixtures.
