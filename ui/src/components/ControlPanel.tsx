interface Props {
  isRunning: boolean;
  onRunFixture: (name: string) => void;
  onRunScan: (kind?: string) => void;
}

const FIXTURES = ["inbound_vague", "outbound_followup", "post_meeting"];

export function ControlPanel({ isRunning, onRunFixture, onRunScan }: Props) {
  return (
    <div className="control-panel">
      <span className="control-label">Run fixture:</span>
      {FIXTURES.map((f) => (
        <button key={f} disabled={isRunning} onClick={() => onRunFixture(f)}>
          {f}
        </button>
      ))}
      <span className="control-divider">|</span>
      <button disabled={isRunning} onClick={() => onRunScan()}>
        Live Scan (all)
      </button>
    </div>
  );
}
