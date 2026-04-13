import { useState } from "react";

interface Props {
  isRunning: boolean;
  onRunFixture: (name: string) => void;
  onRunScan: (kind?: string) => void;
}

const FIXTURE_GROUPS = [
  {
    title: "Inbound vague RA",
    description: "Referral advocate asks to connect without naming a client or reason.",
    fixtures: [
      {
        name: "inbound_vague",
        label: "Wealth manager intro",
        detail: "Generic quick-connect note from Acme Wealth.",
      },
      {
        name: "inbound_vague_cpa",
        label: "CEPA advisor intro",
        detail: "Advisor wants to compare notes, no client context.",
      },
      {
        name: "inbound_vague_banker",
        label: "Market intro call",
        detail: "Advisor works with founders but gives no specific ask.",
      },
    ],
  },
  {
    title: "Outbound RA follow-up",
    description: "IFG already reached out and needs a light, non-pushy nudge.",
    fixtures: [
      {
        name: "outbound_followup",
        label: "Insurance broker",
        detail: "14-day silence after construction-services outreach.",
      },
      {
        name: "outbound_followup_cepa",
        label: "CEPA planning",
        detail: "Succession-planning note has gone unanswered.",
      },
      {
        name: "outbound_followup_broker",
        label: "Roundtable lead",
        detail: "21-day stale thread after sale-readiness discussion.",
      },
    ],
  },
  {
    title: "Post-meeting thank-you",
    description: "Follow-up after a call with concrete callbacks and next steps.",
    fixtures: [
      {
        name: "post_meeting",
        label: "Linwood intro call",
        detail: "Exit timing, 8x EBITDA anchor, customer concentration.",
      },
      {
        name: "post_meeting_founder",
        label: "Apex HVAC owner",
        detail: "Readiness checklist and recurring revenue valuation.",
      },
      {
        name: "post_meeting_ra_intro",
        label: "Referral partner",
        detail: "RA process overview and owner-readiness questions.",
      },
    ],
  },
];

export function ControlPanel({ isRunning, onRunFixture, onRunScan }: Props) {
  const [sending, setSending] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [sendResult, setSendResult] = useState<string | null>(null);
  const [seedResult, setSeedResult] = useState<string | null>(null);

  const handleSeedInbox = async () => {
    setSeeding(true);
    setSeedResult(null);
    try {
      const res = await fetch("/api/seed-inbox", { method: "POST" });
      const data = await res.json();
      if (data.error) {
        setSeedResult(`Error: ${data.error}`);
      } else {
        setSeedResult(`Seeded ${data.seeded} emails`);
      }
    } catch (err) {
      setSeedResult(`Failed: ${err}`);
    } finally {
      setSeeding(false);
    }
  };

  const handleSendSampleEmails = async () => {
    setSending(true);
    setSendResult(null);
    try {
      const res = await fetch("/api/send-sample-emails", { method: "POST" });
      const data = await res.json();
      if (data.error) {
        setSendResult(`Error: ${data.error}`);
      } else {
        setSendResult(`Sent ${data.sent} emails to ${data.target}`);
      }
    } catch (err) {
      setSendResult(`Failed: ${err}`);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="control-panel">
      <div className="fixture-pane">
        <div className="control-label">Run fixture examples</div>
        <div className="fixture-groups">
          {FIXTURE_GROUPS.map((group) => (
            <section className="fixture-group" key={group.title} aria-label={group.title}>
              <div className="fixture-group-heading">
                <span className="fixture-group-title">{group.title}</span>
                <span className="fixture-group-description">{group.description}</span>
              </div>
              <div className="fixture-list">
                {group.fixtures.map((fixture) => (
                  <button
                    className="fixture-button"
                    key={fixture.name}
                    disabled={isRunning}
                    onClick={() => onRunFixture(fixture.name)}
                    type="button"
                  >
                    <span className="fixture-label">{fixture.label}</span>
                    <span className="fixture-detail">{fixture.detail}</span>
                  </button>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>

      <div className="control-actions" aria-label="Live Outlook actions">
        <button disabled={isRunning} onClick={() => onRunScan()} type="button">
          Live Scan (all)
        </button>
        <button disabled={isRunning || seeding} onClick={handleSeedInbox} type="button">
          {seeding ? "Seeding..." : "Seed Inbox"}
        </button>
        <button disabled={isRunning || sending} onClick={handleSendSampleEmails} type="button">
          {sending ? "Sending..." : "Send IFG Samples"}
        </button>
        {(seedResult || sendResult) && (
          <span className="seed-result">{[seedResult, sendResult].filter(Boolean).join(" | ")}</span>
        )}
      </div>
    </div>
  );
}
