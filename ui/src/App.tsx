import { StatusBar } from "./components/StatusBar";
import { ControlPanel } from "./components/ControlPanel";
import { PipelineGraph } from "./components/PipelineGraph";
import { DraftPreview } from "./components/DraftPreview";
import { usePipelineRun } from "./hooks/usePipelineRun";

export default function App() {
  const { state, runFixture, runScan, updateDraft, approveDraft } = usePipelineRun();

  return (
    <div className="app">
      <header className="app-header">
        <h1>IFG Email Drafting Agent</h1>
      </header>
      <StatusBar />
      <ControlPanel
        isRunning={state.isRunning}
        onRunFixture={runFixture}
        onRunScan={runScan}
      />
      <div className="main-layout">
        <div className="graph-panel">
          <PipelineGraph nodeStatuses={state.nodeStatuses} />
        </div>
        <div className="preview-panel">
          <DraftPreview
            state={state}
            onUpdateDraft={updateDraft}
            onApproveDraft={approveDraft}
          />
        </div>
      </div>
    </div>
  );
}
