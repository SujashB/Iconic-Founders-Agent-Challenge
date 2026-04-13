import type { PipelineState } from "../types";

interface Props {
  state: PipelineState;
}

/** Render a flat key-value record as readable plain text lines. */
function renderPlainText(data: Record<string, unknown>): string {
  const lines: string[] = [];
  for (const [key, value] of Object.entries(data)) {
    const label = key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    if (value === null || value === undefined || value === "") continue;
    if (Array.isArray(value)) {
      if (value.length === 0) continue;
      lines.push(`${label}: ${value.join(", ")}`);
    } else if (typeof value === "object") {
      // Nested object — flatten one level
      const nested = value as Record<string, unknown>;
      lines.push(`${label}:`);
      for (const [k, v] of Object.entries(nested)) {
        if (v === null || v === undefined || v === "") continue;
        const subLabel = k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
        lines.push(`  ${subLabel}: ${Array.isArray(v) ? v.join(", ") : String(v)}`);
      }
    } else {
      lines.push(`${label}: ${String(value)}`);
    }
  }
  return lines.join("\n");
}

export function DraftPreview({ state }: Props) {
  const { finalDraft, outlookDraftId, error, nodeDeltas, log } = state;

  // Extract intermediate data to show as it arrives
  const context = nodeDeltas["context_extractor"] as Record<string, unknown> | undefined;
  const sentiment = nodeDeltas["sentiment"] as Record<string, unknown> | undefined;
  const strategy = nodeDeltas["strategy"] as Record<string, unknown> | undefined;
  const critique = nodeDeltas["critic"] as Record<string, unknown> | undefined;
  const draft = nodeDeltas["drafter"] as Record<string, unknown> | undefined;

  return (
    <div className="draft-preview">
      <h3>Pipeline Output</h3>

      {/* Log */}
      <div className="log-section">
        <div className="section-label">Event Log</div>
        <div className="log-box">
          {log.length === 0 && <span className="muted">Waiting...</span>}
          {log.map((l, i) => (
            <div key={i} className="log-line">{l}</div>
          ))}
        </div>
      </div>

      {/* Intermediate state */}
      {context && (
        <div className="data-section">
          <div className="section-label">Context Extracted</div>
          <pre>{renderPlainText(context)}</pre>
        </div>
      )}

      {sentiment && (
        <div className="data-section">
          <div className="section-label">Sentiment Signals</div>
          <pre>{renderPlainText(sentiment)}</pre>
        </div>
      )}

      {strategy && (
        <div className="data-section">
          <div className="section-label">Strategy</div>
          <pre>{renderPlainText(strategy)}</pre>
        </div>
      )}

      {draft && (
        <div className="data-section">
          <div className="section-label">Draft</div>
          <pre>{renderPlainText(draft)}</pre>
        </div>
      )}

      {critique && (
        <div className="data-section">
          <div className="section-label">Critic</div>
          <pre>{renderPlainText(critique)}</pre>
        </div>
      )}

      {/* Final draft */}
      {finalDraft && (
        <div className="data-section final-draft">
          <div className="section-label">Final Draft</div>
          <div className="draft-subject">Subject: {finalDraft.subject}</div>
          <div className="draft-body">{finalDraft.body}</div>
          <div className="draft-sig">{finalDraft.signature}</div>
          {outlookDraftId && (
            <div className="draft-id muted">Saved: {outlookDraftId}</div>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="data-section error-section">
          <div className="section-label">Error</div>
          <pre>{error}</pre>
        </div>
      )}
    </div>
  );
}
