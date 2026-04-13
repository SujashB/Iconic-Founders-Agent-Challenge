import type { Node, Edge } from "@xyflow/react";

const X_LEFT = 50;
const X_RIGHT = 400;
const Y_GAP = 90;

export const PIPELINE_NODES = [
  "trigger_router",
  "classifier",
  "context_extractor",
  "sentiment",
  "strategy",
  "drafter",
  "critic",
  "draft_writer",
  "drop",
] as const;

export type PipelineNodeId = (typeof PIPELINE_NODES)[number];

export const initialNodes: Node[] = [
  { id: "trigger_router",    position: { x: X_LEFT, y: 0 },          data: { label: "Trigger Router" }, type: "pipelineNode" },
  { id: "classifier",        position: { x: X_RIGHT, y: 0 },         data: { label: "Classifier" },     type: "pipelineNode" },
  { id: "context_extractor", position: { x: X_LEFT, y: Y_GAP },      data: { label: "Context Extractor" }, type: "pipelineNode" },
  { id: "sentiment",         position: { x: X_LEFT, y: Y_GAP * 2 },  data: { label: "Sentiment (subagent)" }, type: "pipelineNode" },
  { id: "strategy",          position: { x: X_LEFT, y: Y_GAP * 3 },  data: { label: "Strategy" },       type: "pipelineNode" },
  { id: "drafter",           position: { x: X_LEFT, y: Y_GAP * 4 },  data: { label: "Drafter" },        type: "pipelineNode" },
  { id: "critic",            position: { x: X_LEFT, y: Y_GAP * 5 },  data: { label: "Critic" },         type: "pipelineNode" },
  { id: "draft_writer",      position: { x: X_LEFT, y: Y_GAP * 6 },  data: { label: "Draft Writer" },   type: "pipelineNode" },
  { id: "drop",              position: { x: X_RIGHT, y: Y_GAP },     data: { label: "Drop" },           type: "pipelineNode" },
];

export const initialEdges: Edge[] = [
  { id: "e-tr-cl",  source: "trigger_router",    target: "classifier",        label: "inbound_vague", animated: false },
  { id: "e-tr-ce",  source: "trigger_router",    target: "context_extractor", label: "other",         animated: false },
  { id: "e-cl-ce",  source: "classifier",        target: "context_extractor", label: "vague",         animated: false },
  { id: "e-cl-dr",  source: "classifier",        target: "drop",              label: "drop",          animated: false },
  { id: "e-ce-se",  source: "context_extractor", target: "sentiment",         animated: false },
  { id: "e-se-st",  source: "sentiment",         target: "strategy",          animated: false },
  { id: "e-st-df",  source: "strategy",          target: "drafter",           animated: false },
  { id: "e-df-cr",  source: "drafter",           target: "critic",            animated: false },
  { id: "e-cr-df",  source: "critic",            target: "drafter",           label: "retry",         animated: false, style: { strokeDasharray: "5 5" } },
  { id: "e-cr-dw",  source: "critic",            target: "draft_writer",      label: "pass",          animated: false },
];
