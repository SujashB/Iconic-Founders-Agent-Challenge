# IFG Email Drafting Agent — Challenge #1

An assistant that watches an IFG advisor's Outlook for three specific situations
and prepares a draft reply in the advisor's voice. Drafts land in the Outlook
**Drafts** folder and as markdown files under `outputs/`. Nothing is ever sent
automatically.

The three situations:

1. **Post-meeting follow-up** — a calendar event with an external attendee just
   ended and no thank-you has been sent.
2. **Stale RA follow-up** — an outbound email to a referring advisor (wealth
   manager, lawyer, accountant) has gone N days without a reply.
3. **Vague inbound RA request** — a referring advisor sent a generic "let's
   connect" email with no client context.

For the full design, read [`System Design/implementation_plan.md`](./System%20Design/implementation_plan.md).
For a one-page non-technical explainer, read [`System Design/architecture.md`](./System%20Design/architecture.md).

---

## Repo layout

```
agent_challenge1.py          CLI entry point
email_agent/
  graph.py                   LangGraph StateGraph wiring
  state.py                   Pydantic + TypedDict state schemas
  prompts.py                 IFG voice guide + per-stage system prompts
  llm.py                     ChatOpenAI factory (OpenRouter → Claude)
  config.py                  env-driven config singleton
  outlook_auth.py            one-shot OAuth bootstrap + smoke test
  scanners/                  post_meeting / stale_followup / inbound_vague
  nodes/                     one file per pipeline station
  agents/
    sentiment_agent.py       ReAct subagent (Medallia + heuristic tools)
  tools/
    medallia_sentiment.py    Beam.ai → Medallia Text Analytics → SentimentSignals
    heuristic_sentiment.py   Local keyword/regex scorer (no network)
    o365.py                  shared O365 Account / toolkit factory
fixtures/                    one offline JSON per scenario
outputs/                     markdown copies of the produced drafts
System Design/
  implementation_plan.md     full design doc
  architecture.md            one-page non-technical explainer
```

---

## Setup

### 1. Python environment

```fish
python3 -m venv .venv
source .venv/bin/activate.fish    # bash: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment variables

```fish
cp .env.example .env
```

Then fill in `.env`. The minimum to get an end-to-end run against fixtures
(no Outlook, no Medallia) is just:

```
OPENROUTER_API_KEY=sk-or-v1-...
```

Everything else has graceful fallbacks:

| Section | Required for | Fallback if missing |
|---|---|---|
| `OPENROUTER_API_KEY` | LLM stations (classifier, strategy, drafter, critic, sentiment subagent) | Hard error — pipeline cannot run |
| `MS_CLIENT_ID` / `MS_CLIENT_SECRET` / `MS_TENANT_ID` | Live scanners + writing into Outlook Drafts | Offline-only mode; markdown drafts still written under `outputs/` |
| `BEAM_API_KEY` + `MEDALLIA_*` | Real sentiment scoring | Neutral `SentimentSignals(source="fallback")` — pipeline keeps moving |
| `RA_DOMAIN_ALLOWLIST` | Filtering scanner hits to RAs | Empty list → scanners produce nothing |

### 3. Azure AD app registration (only needed for live Outlook)

1. Go to **Azure Portal → App registrations → New registration**.
2. Name: `IFG Email Drafting Agent`. Account types: *Accounts in this
   organizational directory only*. Redirect URI: *Public client / native
   (mobile & desktop)* → `https://login.microsoftonline.com/common/oauth2/nativeclient`.
3. After creation, copy **Application (client) ID** → `MS_CLIENT_ID` and
   **Directory (tenant) ID** → `MS_TENANT_ID`.
4. **Certificates & secrets → New client secret** → copy the *Value* into
   `MS_CLIENT_SECRET`.
5. **API permissions → Add → Microsoft Graph → Delegated**, add:
   `Mail.ReadWrite`, `Mail.Send`, `Calendars.Read`, `User.Read`, `offline_access`.
   Grant admin consent.
6. First-run auth (interactive browser sign-in, one time):

   ```fish
   python -m email_agent.outlook_auth
   ```

   This stores a refresh token in `o365_token.txt` (gitignored). Subsequent
   runs refresh silently.

---

## Running it

### Against the bundled fixtures (offline, no Outlook, no Medallia)

```fish
# one fixture
python agent_challenge1.py run --fixture fixtures/inbound_vague.json
python agent_challenge1.py run --fixture fixtures/outbound_followup.json
python agent_challenge1.py run --fixture fixtures/post_meeting.json

# all three at once — also regenerates outputs/*.md
python agent_challenge1.py run --all-fixtures
```

Add `--verbose` to stream the state after every node (useful for debugging
strategy / critic decisions):

```fish
python agent_challenge1.py run --fixture fixtures/inbound_vague.json --verbose
```

### Against live Outlook

```fish
# all three scanners
python agent_challenge1.py scan

# single scanner
python agent_challenge1.py scan --kind post_meeting
python agent_challenge1.py scan --kind stale_followup
python agent_challenge1.py scan --kind inbound_vague
```

Each scanner remembers what it has already processed in
`.agent_state/processed_*.json`, so reruns don't double-draft.

---

## What the demo shows

- **`outputs/draft_inbound_vague.md`** — soft qualifying reply to a generic
  wealth-manager outreach. Asks for context once, no pressure, no calendar
  link.
- **`outputs/draft_outbound_followup.md`** — second-touch nudge after 14 days
  of silence with a referring insurance broker. Offers an exit ramp.
- **`outputs/draft_post_meeting.md`** — follow-up after an intro call with a
  founder-CEO exploring a sale. References the specific things he raised
  (multiple anchor, customer concentration, COO succession), restates the two
  things IFG owes him, and books the next checkpoint.

All three follow the IFG voice guide in `email_agent/prompts.py`: senior M&A
register, no "just" / "circle back" / "touch base", no exclamation marks,
exactly one ask per email, first-name signoff.

---

## Notes

- The pipeline is a **workflow**, not an autonomous agent. Each station is a
  named node with explicit edges. The only place control can loop is
  Drafter ↔ Critic, capped at one retry.
- Sentiment is the only third-party non-Microsoft dependency on the hot path.
  It is wrapped behind an `analyze_sentiment` LangChain tool with a strict
  `SENTIMENT_TIMEOUT_S` and a neutral fallback so a Medallia outage degrades
  draft quality but does not block the pipeline.
- The Critic uses the same voice guide as the Drafter to keep them in
  agreement.
