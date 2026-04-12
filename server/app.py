"""FastAPI server that wraps the email-drafting pipeline and streams
node-by-node progress via Server-Sent Events (SSE).

Start with:
    uvicorn server.app:app --port 8000 --reload
"""
from __future__ import annotations

import asyncio
import importlib
import json
import logging
import traceback
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from email_agent.config import CONFIG
from email_agent.graph import build_graph
from email_agent.state import TriggerEvent
from email_agent.tools.o365 import get_account

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")
log = logging.getLogger("server")

app = FastAPI(title="IFG Email Drafting Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

KIND_TO_SCANNER = {
    "post_meeting": "email_agent.scanners.post_meeting",
    "stale_followup": "email_agent.scanners.stale_followup",
    "inbound_vague": "email_agent.scanners.inbound_vague",
}


# ── helpers ──────────────────────────────────────────────────────

def _serialize(obj):
    """Recursively convert Pydantic models, datetimes, Paths to JSON-safe types."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(v) for v in obj]
    return obj


def _sse(event: str, data: dict) -> dict:
    return {"event": event, "data": json.dumps(data, default=str)}


# ── routes ───────────────────────────────────────────────────────

@app.get("/api/status")
def status():
    acct = get_account()
    fixtures = sorted(p.stem for p in CONFIG.fixtures_dir.glob("*.json"))
    return {
        "o365_connected": acct is not None and acct.is_authenticated,
        "openrouter_configured": bool(CONFIG.openrouter_api_key),
        "beam_configured": CONFIG.has_beam_creds,
        "fixtures": fixtures,
    }


@app.get("/api/run/fixture/{name}")
async def run_fixture(name: str):
    fixture_path = CONFIG.fixtures_dir / f"{name}.json"
    if not fixture_path.exists():
        return {"error": f"fixture not found: {name}"}

    async def _stream():
        try:
            data = json.loads(fixture_path.read_text())
            trigger = TriggerEvent(**data)
            graph = build_graph()
            initial_state = {"trigger": trigger, "retry_count": 0}

            yield _sse("pipeline_start", {
                "fixture": name,
                "kind": trigger.kind,
                "ts": datetime.utcnow().isoformat(),
            })

            def run_stream():
                results = []
                for step in graph.stream(initial_state):
                    for node_name, delta in step.items():
                        results.append((node_name, _serialize(delta)))
                return results

            steps = await asyncio.to_thread(run_stream)
            for node_name, delta in steps:
                yield _sse("node_complete", {
                    "node": node_name,
                    "ts": datetime.utcnow().isoformat(),
                    "delta": delta,
                })
                await asyncio.sleep(0.05)  # small gap so the UI can animate

            # final result
            final_state = {}
            for _, delta in steps:
                final_state.update(delta)

            yield _sse("pipeline_done", {
                "ts": datetime.utcnow().isoformat(),
                "final_draft": final_state.get("final_draft"),
                "outlook_draft_id": final_state.get("outlook_draft_id"),
                "error": final_state.get("error"),
            })
        except Exception as exc:
            log.error("pipeline error: %s", traceback.format_exc())
            yield _sse("pipeline_error", {
                "error": str(exc),
                "ts": datetime.utcnow().isoformat(),
            })

    return EventSourceResponse(_stream())


@app.get("/api/run/scan/{kind}")
async def run_scan(kind: str):
    if kind not in KIND_TO_SCANNER:
        return {"error": f"unknown scanner kind: {kind}"}

    async def _stream():
        try:
            scanner = importlib.import_module(KIND_TO_SCANNER[kind])

            yield _sse("scan_start", {"kind": kind, "ts": datetime.utcnow().isoformat()})

            triggers = await asyncio.to_thread(scanner.scan)
            yield _sse("scan_result", {
                "kind": kind,
                "trigger_count": len(triggers),
                "ts": datetime.utcnow().isoformat(),
            })

            graph = build_graph()
            for i, trigger in enumerate(triggers):
                yield _sse("trigger_start", {
                    "index": i,
                    "kind": trigger.kind,
                    "source_ref": trigger.source_ref,
                    "ts": datetime.utcnow().isoformat(),
                })

                def run_stream(t=trigger):
                    results = []
                    for step in graph.stream({"trigger": t, "retry_count": 0}):
                        for node_name, delta in step.items():
                            results.append((node_name, _serialize(delta)))
                    return results

                steps = await asyncio.to_thread(run_stream)
                for node_name, delta in steps:
                    yield _sse("node_complete", {
                        "node": node_name,
                        "ts": datetime.utcnow().isoformat(),
                        "delta": delta,
                    })
                    await asyncio.sleep(0.05)

                final_state = {}
                for _, delta in steps:
                    final_state.update(delta)

                yield _sse("trigger_done", {
                    "index": i,
                    "final_draft": final_state.get("final_draft"),
                    "outlook_draft_id": final_state.get("outlook_draft_id"),
                    "error": final_state.get("error"),
                    "ts": datetime.utcnow().isoformat(),
                })

            yield _sse("scan_done", {"kind": kind, "ts": datetime.utcnow().isoformat()})
        except Exception as exc:
            log.error("scan error: %s", traceback.format_exc())
            yield _sse("pipeline_error", {
                "error": str(exc),
                "ts": datetime.utcnow().isoformat(),
            })

    return EventSourceResponse(_stream())


@app.get("/api/run/scan")
async def run_scan_all():
    """Run all 3 scanners sequentially."""
    async def _stream():
        for kind, module_path in KIND_TO_SCANNER.items():
            try:
                scanner = importlib.import_module(module_path)
                yield _sse("scan_start", {"kind": kind, "ts": datetime.utcnow().isoformat()})
                triggers = await asyncio.to_thread(scanner.scan)
                yield _sse("scan_result", {
                    "kind": kind,
                    "trigger_count": len(triggers),
                    "ts": datetime.utcnow().isoformat(),
                })

                graph = build_graph()
                for trigger in triggers:
                    def run_stream(t=trigger):
                        results = []
                        for step in graph.stream({"trigger": t, "retry_count": 0}):
                            for node_name, delta in step.items():
                                results.append((node_name, _serialize(delta)))
                        return results

                    steps = await asyncio.to_thread(run_stream)
                    for node_name, delta in steps:
                        yield _sse("node_complete", {
                            "node": node_name,
                            "ts": datetime.utcnow().isoformat(),
                            "delta": delta,
                        })
                        await asyncio.sleep(0.05)

                yield _sse("scan_done", {"kind": kind, "ts": datetime.utcnow().isoformat()})
            except Exception as exc:
                log.error("scan error for %s: %s", kind, exc)
                yield _sse("scan_done", {
                    "kind": kind,
                    "error": str(exc),
                    "ts": datetime.utcnow().isoformat(),
                })

    return EventSourceResponse(_stream())
