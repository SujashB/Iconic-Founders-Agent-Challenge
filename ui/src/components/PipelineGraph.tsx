import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  type Node,
  type Edge,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { initialNodes, initialEdges } from "../graphLayout";
import { NodeBox } from "./NodeBox";
import type { NodeStatus } from "../types";

interface Props {
  nodeStatuses: Record<string, NodeStatus>;
}

const nodeTypes: NodeTypes = { pipelineNode: NodeBox };

export function PipelineGraph({ nodeStatuses }: Props) {
  const nodes: Node[] = useMemo(
    () =>
      initialNodes.map((n) => ({
        ...n,
        data: { ...n.data, status: nodeStatuses[n.id] || "idle" },
      })),
    [nodeStatuses]
  );

  const edges: Edge[] = useMemo(() => {
    return initialEdges.map((e) => ({
      ...e,
      animated: nodeStatuses[e.source] === "complete" && nodeStatuses[e.target] !== "idle",
      style: {
        ...e.style,
        stroke: "#000",
        strokeWidth: 1.5,
      },
    }));
  }, [nodeStatuses]);

  return (
    <div style={{ width: "100%", height: "100%" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        zoomOnDoubleClick={false}
      >
        <Background color="#eee" gap={20} />
      </ReactFlow>
    </div>
  );
}
