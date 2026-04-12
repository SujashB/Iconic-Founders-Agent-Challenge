import type { PipelineState } from "../types";

interface Props {
  state: PipelineState;
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
          <pre>{JSON.stringify(context, null, 2)}</pre>
        </div>
      )}

      {sentiment && (
        <div className="data-section">
          <div className="section-label">Sentiment Signals</div>
          <pre>{JSON.stringify(sentiment, null, 2)}</pre>
        </div>
      )}

      {strategy && (
        <div className="data-section">
          <div className="section-label">Strategy</div>
          <pre>{JSON.stringify(strategy, null, 2)}</pre>
        </div>
      )}

      {draft && (
        <div className="data-section">
          <div className="section-label">Draft</div>
          <pre>{JSON.stringify(draft, null, 2)}</pre>
        </div>
      )}

      {critique && (
        <div className="data-section">
          <div className="section-label">Critic</div>
          <pre>{JSON.stringify(critique, null, 2)}</pre>
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
