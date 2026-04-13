# IFG Email Drafting Agent Demo Script

## Audience

This script is written for M&A advisors, referral relationship owners, and firm leadership. Keep the demo focused on business outcomes: faster follow-up, better referral partner experience, consistent advisor voice, and human control.

## Pre-Demo Setup

Have the app open before the meeting:

- API server running.
- Web interface running.
- Browser open to `http://localhost:5173`.
- Use fixture examples for the cleanest demo. Use Live Scan only if Outlook is connected and the demo inbox has been prepared.

Opening line:

"This is a drafting assistant for routine but important relationship emails. It watches for a few high-value moments in an advisor's day, drafts the follow-up, and leaves the advisor in control. Nothing is sent automatically."

## 1. Start On The Home Screen

What to click: nothing yet.

What to say:

"At the top, we can see the system status. Outlook tells us whether the mailbox connection is live. The drafting engine tells us whether the local writing model is ready. Medallia tells us whether the sentiment read is using the external service or the fallback. The important point is that the advisor is not starting from a blank page. The system is watching for moments that already matter in advisory work."

Business framing:

"In M&A advisory, the risk is not usually that nobody knows what to write. The risk is that follow-up gets delayed, sounds too generic, or fails to reference the actual deal context. This tool is built to protect those moments."

## 2. Run The First Scenario: Vague Referral Partner Outreach

What to click:

1. Under **Run fixture examples**, find **Inbound vague RA**.
2. Click **Wealth manager intro**.

What is happening:

"This simulates a wealth manager sending a warm but vague note: 'Would be good to connect,' without naming a client, transaction, timing, or reason for the call."

What to say while the graph runs:

"The workflow is moving left to right and top to bottom. First it identifies the type of situation. Because this is a vague referral partner note, it adds an extra check: is there enough business context here, or should the reply ask one clean qualifying question?"

As sections appear in **Pipeline Output**, say:

"The context section pulls out the useful relationship facts, such as who sent the note and what is missing. The sentiment section looks for tone and urgency. The strategy section decides how the advisor should respond. In this case, we do not want to rush into a calendar link. We want to acknowledge the relationship and ask for enough context to make the next conversation productive."

When **Review and Edit Draft** appears:

"Now the system has produced a first draft, but it has not sent anything. The advisor can edit the subject, body, or signature. This matters because a referral partner relationship is not a place to automate judgment. The tool removes the blank page; the advisor still owns the relationship."

What to click:

1. Click in the **Body** field.
2. Make a small edit, for example adding a more specific phrase such as "happy to compare notes once I understand the situation."
3. Click **Approve and Save**.

What to say:

"Approval records the human-reviewed version. In a live setup, it can also leave the final version in Outlook Drafts. The advisor still decides whether and when to send it."

## 3. Run The Second Scenario: Quiet Referral Partner Thread

What to click:

1. Under **Outbound RA follow-up**, click **Insurance broker**.

What is happening:

"This is the common second-touch problem. IFG reached out to a referral partner after a mutual contact surfaced potential construction-services owners. Fourteen days have passed without a reply."

What to say while the graph runs:

"The system is not trying to be aggressive. In advisory work, a follow-up should keep the door open without making the relationship feel transactional. The strategy step is deciding how to nudge while preserving optionality."

When the draft appears:

"Notice the goal of this draft: one light ask, no pressure, and a graceful exit ramp. That is the right posture for a referral advocate. We are reminding them why the conversation was relevant without forcing a response."

Optional edit:

"If the advisor knows more about the relationship, they can add it here before saving. For example, they might reference the mutual contact or the sector conversation. The tool gives the advisor a strong starting point, not a locked script."

What to click:

1. Review the subject and body.
2. Click **Approve and Save**.

## 4. Run The Third Scenario: Founder Post-Meeting Follow-Up

What to click:

1. Under **Post-meeting thank-you**, click **Linwood intro call**.

What is happening:

"This scenario follows an intro call with a founder-CEO exploring a sale in the next 18 to 24 months. The meeting included real deal context: valuation expectations, customer concentration, succession questions, and follow-up items IFG promised."

What to say while the graph runs:

"This is where specificity matters. A generic 'great speaking today' email weakens momentum. The system is looking for the founder's concerns and the commitments IFG made, then turning those into a concise follow-up."

As **Context Extracted** appears:

"Here we can see the system pulling out the points an advisor would normally have to reconstruct from notes: the 8x EBITDA anchor, the top-customer concentration issue, the COO succession concern, and the agreed next steps."

As **Strategy** appears:

"The strategy is deciding how to sound like a senior advisor: calm, specific, and useful. It should not overpromise. It should not sound like a sales email. It should confirm the next step and keep the founder's trust."

When the draft appears:

"This is the most advisory-facing example. The draft references the founder's situation and repeats what IFG owes him next. That keeps momentum without turning the email into a long memo."

What to click:

1. Read the draft.
2. Optionally edit the **Body** to add a personal note from the call.
3. Click **Approve and Save**.

What to say:

"The takeaway is that the advisor is not outsourcing judgment. The advisor is compressing the administrative work between a good conversation and a good follow-up."

## 5. Show Live Outlook Mode

Use this section only if Outlook is connected.

What to click:

1. Click **Live Scan (all)**.

What is happening:

"Instead of using sample data, the tool scans the advisor's actual Outlook environment for the three situations: a meeting that just ended, a quiet referral thread, or a vague inbound referral note."

What to say:

"This is the operating model for a real advisory desk. The system checks for the moments where follow-up usually matters most, drafts the response, and leaves it for review. It also remembers what it has already processed so the same thread does not create duplicate drafts."

Optional demo inbox actions:

- Click **Seed Inbox** if you need to place sample inbound messages into the demo inbox.
- Click **Send IFG Samples** if you need to send sample IFG-generated replies to the configured demo target.

How to describe those buttons:

"These are demo helpers. They let us stage sample messages in a controlled inbox so we can show the live scanner without waiting for real relationship traffic."

## 6. Close The Demo

Closing line:

"The product is intentionally narrow. It is not trying to run a deal process or replace an advisor. It handles the routine relationship follow-ups that are easy to delay and costly to make generic. The advisor reviews every draft, the firm's voice stays consistent, and the relationship touchpoints happen faster."

Key takeaways:

- Faster response to founders and referral partners.
- More consistent IFG tone across advisors.
- Better use of meeting and thread context.
- Human review before anything is sent.
- A reviewable record of approved drafts.

## Short Version

Use this if you only have two minutes:

1. Open `http://localhost:5173`.
2. Click **Wealth manager intro**.
3. Explain that the system detects a vague referral partner note and asks for useful context instead of sending a generic calendar link.
4. Review the generated draft and click **Approve and Save**.
5. Click **Linwood intro call**.
6. Explain that the system turns founder meeting context into a specific follow-up with next steps.
7. Close with: "The advisor stays in control. The tool just makes sure the important follow-up is timely, specific, and on-voice."
