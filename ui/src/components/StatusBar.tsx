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

  return (
    <div className="status-bar">
      <span className="status-item">
        <span className={`dot ${status.o365_connected ? "on" : "off"}`} />
        Outlook: {status.o365_connected ? "Connected" : "Offline"}
      </span>
      <span className="status-item">
        <span className={`dot ${status.openrouter_configured ? "on" : "off"}`} />
        OpenRouter: {status.openrouter_configured ? "Configured" : "No Key"}
      </span>
      <span className="status-item">
        <span className={`dot ${status.beam_configured ? "on" : "off"}`} />
        Medallia: {status.beam_configured ? "Configured" : "Fallback"}
      </span>
    </div>
  );
}
