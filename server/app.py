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
from pydantic import BaseModel
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
async def status():
    acct = get_account()
    fixtures = sorted(p.stem for p in CONFIG.fixtures_dir.glob("*.json"))

    # Check Composio MCP connectivity
    composio_connected = False
    composio_tools: list[str] = []
    if CONFIG.has_composio:
        try:
            from email_agent.tools.composio_outlook import list_tools_sync
            tools = await asyncio.to_thread(list_tools_sync)
            composio_connected = len(tools) > 0
            composio_tools = [t["name"] for t in tools]
        except Exception as exc:
            log.warning("composio status check failed: %s", exc)

    return {
        "o365_connected": acct is not None and acct.is_authenticated,
        "composio_configured": CONFIG.has_composio,
        "composio_connected": composio_connected,
        "composio_tools": composio_tools,
        "llm_provider": "ollama",
        "llm_model": CONFIG.ollama_model,
        "sentiment_llm_model": CONFIG.sentiment_ollama_model,
        "llm_configured": bool(CONFIG.ollama_model and CONFIG.ollama_base_url),
        "beam_configured": CONFIG.has_beam_creds,
        "fixtures": fixtures,
    }


@app.get("/api/mcp/tools")
async def mcp_tools():
    """List all available Composio MCP tools."""
    if not CONFIG.has_composio:
        return {"error": "Composio not configured", "tools": []}
    try:
        from email_agent.tools.composio_outlook import list_tools_sync
        tools = await asyncio.to_thread(list_tools_sync)
        return {"tools": tools}
    except Exception as exc:
        log.error("mcp tools listing failed: %s", exc)
        return {"error": str(exc), "tools": []}


class ApprovedDraft(BaseModel):
    subject: str
    body: str
    signature: str


@app.post("/api/draft/approve")
async def approve_draft(draft: ApprovedDraft):
    """Save a human-reviewed (and possibly edited) draft to disk and optionally Outlook."""
    rendered = (
        f"# Approved Draft\n\n"
        f"**Subject:** {draft.subject}\n\n"
        f"---\n\n"
        f"{draft.body}\n\n"
        f"{draft.signature}\n"
    )
    out_path = CONFIG.outputs_dir / f"approved_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.md"
    out_path.write_text(rendered)
    log.info("approved draft written to %s", out_path)

    # Try writing to Outlook Drafts if connected
    outlook_id = None
    try:
        from email_agent.tools.o365 import get_tool
        create_tool = get_tool("create_email_draft") or get_tool("O365CreateDraftMessage")
        if create_tool is not None:
            body_html = draft.body.replace("\n", "<br>") + "<br><br>" + draft.signature.replace("\n", "<br>")
            result = create_tool.invoke({"subject": draft.subject, "body": body_html, "to": []})
            outlook_id = str(result)
    except Exception as exc:
        log.warning("outlook draft creation skipped: %s", exc)

    return {
        "saved_to": str(out_path),
        "outlook_draft_id": outlook_id,
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


SAMPLE_EMAILS = [
    {
        "sender_name": "Marcus Webb",
        "sender_email": "marcus@acmewealth.com",
        "subject": "Quick connect?",
        "body": (
            "Hi Sam,\n\nHope you're doing well. I came across IFG through a colleague "
            "and wanted to see if there might be a good time for a quick chat in the "
            "coming weeks. Always interesting to swap notes with folks in the M&A "
            "advisory space.\n\nLet me know what works.\n\nBest,\nMarcus\n"
            "Acme Wealth Partners"
        ),
    },
    {
        "sender_name": "Jennifer Liu",
        "sender_email": "jliu@buildright-insurance.com",
        "subject": "Possible intro — client exploring options",
        "body": (
            "Sam,\n\nOne of our portfolio company founders has been asking questions "
            "about timing for a sale process. Revenue is in the $15-20M range, "
            "SaaS vertical. Thought IFG might be a good fit. Can we set up a call "
            "this week?\n\nThanks,\nJennifer Liu\nSilverline Capital Partners"
        ),
    },
    {
        "sender_name": "Robert Chen",
        "sender_email": "robert.chen@cepa-advisors.com",
        "subject": "Re: Follow-up from industry event",
        "body": (
            "Hi Sam,\n\nGreat meeting you at the PE conference last week. I wanted "
            "to follow up on our conversation about deal flow in the healthcare "
            "services sector. We have a few clients in that space who might benefit "
            "from IFG's approach.\n\nWould love to continue the conversation. "
            "What does your schedule look like?\n\nBest regards,\nRobert Chen\n"
            "Apex Advisory Group"
        ),
    },
]

SAMPLE_EMAIL_TARGET = "sjbarman@ucdavis.edu"
SAMPLE_FIXTURE_NAMES = ["inbound_vague", "outbound_followup", "post_meeting"]


@app.post("/api/seed-inbox")
async def seed_inbox():
    """Place raw sample emails into the connected Outlook inbox for live scans."""
    if not CONFIG.has_composio:
        return {"error": "Composio not configured"}

    from email_agent.tools.composio_outlook import seed_message_to_inbox

    results = []
    for email in SAMPLE_EMAILS:
        try:
            sender_name = email.get("sender_name", "External Contact")
            sender_email = email.get("sender_email", "")
            if not sender_email:
                raise ValueError("sample email is missing sender_email")
            result = await asyncio.to_thread(
                seed_message_to_inbox,
                email["subject"],
                email["body"],
                sender_name,
                sender_email,
            )
            if result is None:
                raise RuntimeError("Composio seed operation returned no result")
            results.append({"subject": email["subject"], "status": "seeded", "result": str(result)})
        except Exception as exc:
            results.append({"subject": email["subject"], "status": "error", "error": str(exc)})
    seeded = sum(result["status"] == "seeded" for result in results)
    return {"seeded": seeded, "results": results}


def _build_ifg_sample_email(fixture_name: str) -> tuple[str, str]:
    fixture_path = CONFIG.fixtures_dir / f"{fixture_name}.json"
    data = json.loads(fixture_path.read_text())
    trigger = TriggerEvent(**data)
    result = build_graph().invoke({"trigger": trigger, "retry_count": 0})
    draft = result.get("final_draft")
    if draft is None:
        raise RuntimeError(result.get("error") or f"no draft produced for {fixture_name}")
    return draft.subject, f"{draft.body}\n\n{draft.signature}".strip()


@app.post("/api/send-sample-emails")
async def send_sample_emails():
    """Generate IFG draft replies from fixtures and send them to the demo inbox."""
    if not CONFIG.has_composio:
        return {"error": "Composio not configured"}

    from email_agent.tools.composio_outlook import send_email

    results = []
    for fixture_name in SAMPLE_FIXTURE_NAMES:
        try:
            subject, body = await asyncio.to_thread(_build_ifg_sample_email, fixture_name)
            result = await asyncio.to_thread(send_email, SAMPLE_EMAIL_TARGET, subject, body)
            if result is None:
                raise RuntimeError("Composio OUTLOOK_SEND_EMAIL returned no result")
            results.append({"fixture": fixture_name, "subject": subject, "status": "sent", "result": str(result)})
        except Exception as exc:
            results.append({"fixture": fixture_name, "status": "error", "error": str(exc)})
    sent = sum(result["status"] == "sent" for result in results)
    return {"target": SAMPLE_EMAIL_TARGET, "sent": sent, "results": results}


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
