import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { NodeStatus } from "../types";

const STATUS_STYLES: Record<NodeStatus, React.CSSProperties> = {
  idle: { background: "#fff", color: "#000", border: "2px solid #000" },
  active: { background: "#000", color: "#fff", border: "2px solid #000" },
  complete: { background: "#fff", color: "#000", border: "2px solid #000" },
  skipped: { background: "#fff", color: "#999", border: "2px dashed #999" },
  error: { background: "#fff", color: "#000", border: "2px dashed #000" },
};

export function NodeBox({ data }: NodeProps) {
  const status = (data.status as NodeStatus) || "idle";
  const style = STATUS_STYLES[status];

  return (
    <div
      style={{
        ...style,
        padding: "10px 18px",
        borderRadius: 4,
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: 13,
        minWidth: 160,
        textAlign: "center",
        position: "relative",
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: "#000" }} />
      <div style={{ fontWeight: 600 }}>{data.label as string}</div>
      {status === "complete" && (
        <span style={{ position: "absolute", top: 4, right: 8, fontSize: 11 }}>
          &#10003;
        </span>
      )}
      {status === "active" && (
        <span style={{ position: "absolute", top: 4, right: 8, fontSize: 11 }}>
          ...
        </span>
      )}
      <Handle type="source" position={Position.Bottom} style={{ background: "#000" }} />
    </div>
  );
}
