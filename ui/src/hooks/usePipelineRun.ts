import { useCallback, useRef, useState } from "react";
import type { NodeStatus, PipelineState } from "../types";
import { PIPELINE_NODES } from "../graphLayout";

const INITIAL: PipelineState = {
  nodeStatuses: Object.fromEntries(PIPELINE_NODES.map((n) => [n, "idle" as NodeStatus])),
  nodeDeltas: {},
  finalDraft: null,
  outlookDraftId: null,
  error: null,
  isRunning: false,
  log: [],
  approved: false,
};

export function usePipelineRun() {
  const [state, setState] = useState<PipelineState>(INITIAL);
  const esRef = useRef<EventSource | null>(null);

  const addLog = (msg: string) =>
    setState((s) => ({ ...s, log: [...s.log, msg] }));

  const setNodeStatus = (node: string, status: NodeStatus) =>
    setState((s) => ({
      ...s,
      nodeStatuses: { ...s.nodeStatuses, [node]: status },
    }));

  const stop = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    setState((s) => ({ ...s, isRunning: false }));
  }, []);

  const start = useCallback(
    (url: string) => {
      // reset
      setState({
        ...INITIAL,
        nodeStatuses: Object.fromEntries(
          PIPELINE_NODES.map((n) => [n, "idle" as NodeStatus])
        ),
        isRunning: true,
        log: [],
      });

      const es = new EventSource(url);
      esRef.current = es;

      es.addEventListener("pipeline_start", (e) => {
        const d = JSON.parse(e.data);
        addLog(`Pipeline started: ${d.kind} (${d.fixture ?? "scan"})`);
      });

      es.addEventListener("node_complete", (e) => {
        const d = JSON.parse(e.data);
        const node = d.node as string;
        setState((s) => ({
          ...s,
          nodeStatuses: { ...s.nodeStatuses, [node]: "complete" },
          nodeDeltas: { ...s.nodeDeltas, [node]: d.delta },
          log: [...s.log, `[${node}] complete`],
        }));
      });

      es.addEventListener("pipeline_done", (e) => {
        const d = JSON.parse(e.data);
        setState((s) => ({
          ...s,
          finalDraft: d.final_draft,
          outlookDraftId: d.outlook_draft_id,
          error: d.error,
          isRunning: false,
          log: [...s.log, d.error ? `Error: ${d.error}` : "Pipeline done"],
        }));
        es.close();
      });

      es.addEventListener("pipeline_error", (e) => {
        const d = JSON.parse(e.data);
        setState((s) => ({
          ...s,
          error: d.error,
          isRunning: false,
          log: [...s.log, `Error: ${d.error}`],
        }));
        es.close();
      });

      es.addEventListener("scan_start", (e) => {
        const d = JSON.parse(e.data);
        addLog(`Scanning: ${d.kind}`);
      });

      es.addEventListener("scan_result", (e) => {
        const d = JSON.parse(e.data);
        addLog(`${d.kind}: ${d.trigger_count} trigger(s) found`);
      });

      es.addEventListener("scan_done", (e) => {
        const d = JSON.parse(e.data);
        addLog(`Scan complete: ${d.kind}`);
        setState((s) => ({ ...s, isRunning: false }));
        es.close();
      });

      es.onerror = () => {
        addLog("Connection lost");
        setState((s) => ({ ...s, isRunning: false }));
        es.close();
      };
    },
    []
  );

  const runFixture = useCallback(
    (name: string) => start(`/api/run/fixture/${name}`),
    [start]
  );

  const runScan = useCallback(
    (kind?: string) =>
      start(kind ? `/api/run/scan/${kind}` : "/api/run/scan"),
    [start]
  );

  const updateDraft = useCallback(
    (field: "subject" | "body" | "signature", value: string) => {
      setState((s) => {
        if (!s.finalDraft) return s;
        return {
          ...s,
          finalDraft: { ...s.finalDraft, [field]: value },
        };
      });
    },
    []
  );

  const approveDraft = useCallback(async () => {
    if (!state.finalDraft) return;
    try {
      const res = await fetch("/api/draft/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(state.finalDraft),
      });
      const data = await res.json();
      if (data.error) {
        addLog(`Approve failed: ${data.error}`);
      } else {
        addLog(`Draft approved and saved: ${data.saved_to}`);
        setState((s) => ({ ...s, approved: true }));
      }
    } catch (err) {
      addLog(`Approve failed: ${err}`);
    }
  }, [state.finalDraft]);

  return { state, runFixture, runScan, stop, setNodeStatus, updateDraft, approveDraft };
}
