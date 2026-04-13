import { useEffect, useState } from "react";
import { fetchStatus } from "../api/statusApi";
import type { StatusResponse } from "../types";

export function StatusBar() {
  const [status, setStatus] = useState<StatusResponse | null>(null);

  useEffect(() => {
    fetchStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  if (!status) {
    return <div className="status-bar">Loading status...</div>;
  }

  const outlookConnected = status.composio_connected || status.o365_connected;

  return (
    <div className="status-bar">
      <span className="status-item">
        <span className={`dot ${outlookConnected ? "on" : "off"}`} />
        Outlook (MCP):{" "}
        {status.composio_connected
          ? `Connected (${status.composio_tools.length} tools)`
          : status.o365_connected
            ? "Connected (O365)"
            : "Offline"}
      </span>
      <span className="status-item">
        <span className={`dot ${status.llm_configured ? "on" : "off"}`} />
        LLM:{" "}
        {status.llm_configured
          ? `${status.llm_provider} / ${status.llm_model}; sentiment ${status.sentiment_llm_model}`
          : "Offline"}
      </span>
      <span className="status-item">
        <span className={`dot ${status.beam_configured ? "on" : "off"}`} />
        Medallia: {status.beam_configured ? "Configured" : "Fallback"}
      </span>
    </div>
  );
}
