# IFG Email Drafting Agent

## What Is This?

This is an internal tool that helps IFG advisors write relationship emails faster and more consistently. It watches an advisor's Outlook inbox, spots situations that need a reply, and produces a ready-to-edit draft. The advisor reviews and approves every email before it goes out — the tool never sends anything on its own.

Think of it as a junior associate who reads your inbox, knows how IFG likes to communicate, and leaves a polished first draft on your desk every morning. You still decide what gets sent.

---

## The Problem It Solves

Advisors juggle dozens of active relationships: founders exploring a sale, wealth managers sending referrals, attorneys coordinating due diligence. Each conversation generates follow-up emails that should go out the same day — thank-you notes after calls, nudges on quiet threads, replies to warm introductions.

In practice, these emails slip. A busy deal week means a referral partner's introduction sits unanswered for three days, or a post-meeting thank-you never gets written. The emails themselves are not complicated, but the volume adds up, and each missed or delayed response chips away at the firm's reputation with the people who send it business.

This tool closes that gap. It drafts the routine relationship emails so advisors can focus on the conversations themselves, not the follow-up paperwork.

---

## What It Watches For

The agent monitors three specific situations in an advisor's Outlook:

| Situation | What Happens | Why It Matters |
|---|---|---|
| **A meeting just ended** | The tool sees a completed calendar event with an external attendee and drafts a thank-you or recap email | Fast follow-up signals professionalism and keeps deal momentum alive |
| **A referral partner has gone quiet** | An outbound email to a wealth manager, attorney, or accountant has had no reply for several days | Gentle nudges keep referral pipelines warm without being pushy |
| **A vague introduction came in** | A referral partner sent a generic "you should talk to my client" email with no detail | The draft asks a qualifying question to move the conversation forward instead of sending a generic "let's find time" |

These three scenarios cover the bulk of routine relationship correspondence in a typical advisory week.

---

## How an Advisor Uses It

1. **The tool watches your inbox.** It scans Outlook for meetings that just ended, emails that have gone quiet, and inbound notes from known referral partners.
2. **It writes a first draft.** For each situation it finds, it runs the email through a multi-step quality process: understand the context, read the tone of the conversation, pick the right approach, write the draft, and review it for quality.
3. **You review and edit.** The draft appears in a simple web interface. You can change the subject line, rewrite any paragraph, or adjust the sign-off.
4. **You approve it.** One click saves the final version to your Outlook Drafts folder, ready to send. Nothing leaves your outbox without your approval.

The advisor stays in control at every step. The tool handles the blank-page problem; the advisor handles the judgment calls.

---

## Who Benefits

- **Advisors** get time back. Instead of writing every follow-up from scratch, they start with a draft that already captures the right tone and references the actual conversation. Faster response times, fewer emails that fall through the cracks.

- **Operations and support staff** gain visibility. Every draft is logged, creating a clear audit trail of what outreach is happening and when — without anyone needing to dig through sent mail.

- **Firm leadership** gets consistency. When five advisors each write in their own style, the firm's voice fragments. This tool anchors every draft to IFG's communication guidelines, so whether an email comes from a senior partner or a newer team member, it reads the same: calm, specific, and senior.

- **Referral advocates** on the receiving end get better emails. A wealth manager who sends IFG a vague introduction gets a reply that moves the conversation forward, not a generic acknowledgment. That responsiveness strengthens the referral relationship over time.

---

## The Review Step (Human-in-the-Loop)

Every draft the tool produces lands in an editable review panel. The advisor can read the generated subject line, body, and signature, then modify any part before approving. Nothing is sent or finalized until a human clicks **Approve and Save**.

This is a deliberate design choice. Relationship emails in M&A carry real stakes — a poorly worded follow-up to a referral partner can cool a warm introduction, and an overly aggressive nudge can damage a long-term relationship. The tool accelerates the work; the advisor owns the judgment.

---

## How It Works (Under the Hood)

For those who want the technical detail, the tool is built as a multi-step pipeline. Each email passes through these stages:

```
Classify the situation -> Extract context -> Analyze tone -> Pick a strategy -> Write the draft -> Review for quality -> Save
```

- **Classify**: Determine which of the three scenarios this email falls into.
- **Extract context**: Pull out names, companies, topics, and meeting details from the email thread or calendar event.
- **Analyze tone**: Read the sentiment of the incoming message so the reply matches the right emotional register.
- **Pick a strategy**: Choose the drafting approach (e.g., warm thank-you vs. qualifying question vs. gentle nudge).
- **Write the draft**: Generate the email using IFG's voice guidelines.
- **Review for quality**: A second pass checks the draft for tone, completeness, and professionalism. If it falls short, the draft is rewritten once.
- **Save**: The approved draft is stored in Outlook Drafts and logged as a file for the audit trail.

The language model runs locally on the firm's own hardware — no email content is sent to external AI services.

---

## Technical Setup

This section is for the engineering team or IT staff responsible for deploying and maintaining the tool.

### Prerequisites

- Python 3.12+
- Node.js 18+ and npm (for the web interface)
- Ollama (local language model server)

### 1. Clone and set up Python

```bash
git clone <repo-url>
cd Iconic-Founders-Agent-Challenge
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install and start the language models

```bash
ollama serve
ollama pull qwen3:1.7b
ollama pull deepseek-r1:1.5b
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in the values. For offline testing with sample data, a running Ollama server is all that is needed.

| Variable Group | Required For | Fallback |
|---|---|---|
| `OLLAMA_MODEL` / `OLLAMA_BASE_URL` | Language model | Defaults to `qwen3:1.7b` at `localhost:11434` |
| `SENTIMENT_OLLAMA_MODEL` | Tone analysis | Defaults to `deepseek-r1:1.5b`; local fallback available |
| `MS_CLIENT_ID` / `MS_CLIENT_SECRET` / `MS_TENANT_ID` | Live Outlook connection | Offline mode; drafts still written to `outputs/` |
| `BEAM_API_KEY` + `MEDALLIA_*` | External sentiment service | Neutral fallback, pipeline continues |
| `RA_DOMAIN_ALLOWLIST` | Filtering inbox results | Empty means scanners produce nothing |

### 4. Install the web interface

```bash
cd ui
npm install
```

### 5. Azure AD setup (only for live Outlook)

1. Go to Azure Portal > App registrations > New registration
2. Redirect URI: Public client with `https://login.microsoftonline.com/common/oauth2/nativeclient`
3. Copy Client ID and Tenant ID into `.env`
4. Create a client secret, copy into `.env`
5. API permissions: add `Mail.ReadWrite`, `Mail.Send`, `Calendars.Read`, `User.Read`, `offline_access` (delegated). Grant admin consent.
6. Run once: `python -m email_agent.outlook_auth`

---

## Running the Tool

### From the command line (using sample data)

```bash
# Single test case
python agent_challenge1.py run --fixture fixtures/inbound_vague.json

# All test cases
python agent_challenge1.py run --all-fixtures

# Verbose mode (shows each pipeline step)
python agent_challenge1.py run --fixture fixtures/post_meeting.json --verbose
```

### From the command line (live Outlook)

```bash
# All scanners
python agent_challenge1.py scan

# Single scanner
python agent_challenge1.py scan --kind post_meeting
python agent_challenge1.py scan --kind stale_followup
python agent_challenge1.py scan --kind inbound_vague
```

### Web interface

Start the backend and frontend in separate terminals:

```bash
# Terminal 1: API server
uvicorn server.app:app --port 8000 --reload

# Terminal 2: Web interface
cd ui
npm run dev
```

Open `http://localhost:5173` in a browser. The web interface connects to the backend automatically.

### Tests

```bash
python -m pytest tests/
```

---

## Project Structure

For developers working on the codebase:

```
agent_challenge1.py              CLI entry point
server/
  app.py                         API server with live streaming + draft approval
email_agent/
  graph.py                       Pipeline wiring
  state.py                       Data schemas
  prompts.py                     IFG voice guide + per-stage instructions
  llm.py                         Language model configuration
  config.py                      Environment-driven settings
  outlook_auth.py                One-time OAuth setup
  nodes/                         Pipeline stages (one file each):
    trigger_router.py              Route trigger to the right handler
    classifier.py                  Classify the email scenario
    context_extractor.py           Extract names, companies, topics
    sentiment.py                   Analyze tone
    strategy.py                    Select drafting approach
    drafter.py                     Generate the draft
    critic.py                      Review and optionally rewrite
    draft_writer.py                Save final draft to Outlook + disk
  scanners/                      Outlook inbox scanners:
    post_meeting.py                Post-meeting follow-up scanner
    stale_followup.py              Stale RA follow-up scanner
    inbound_vague.py               Vague inbound RA scanner
    _dedupe.py                     Deduplication helpers
  agents/
    sentiment_agent.py             Tone analysis subagent
  tools/
    medallia_sentiment.py          External sentiment integration
    heuristic_sentiment.py         Local keyword/regex scorer
    o365.py                        Outlook account factory
    composio_outlook.py            Alternative Outlook integration
fixtures/                        Sample test cases (3 per scenario)
outputs/                         Generated draft files
tests/
  test_fixtures.py               Automated tests
ui/                              Web interface (React + TypeScript)
  src/
    App.tsx                        Main app component
    types.ts                       Shared types
    graphLayout.ts                 Pipeline visualization layout
    hooks/usePipelineRun.ts        Live streaming hook
    api/statusApi.ts               Backend connection
    components/
      PipelineGraph.tsx            Interactive pipeline diagram
      ControlPanel.tsx             Run controls
      DraftPreview.tsx             Draft display with editing
      StatusBar.tsx                Connection indicators
      NodeBox.tsx                  Pipeline node component
System Design/
  architecture.md                Non-technical architecture overview
  implementation_plan.md         Full design document
Problem_Statement/               Original assignment
```
