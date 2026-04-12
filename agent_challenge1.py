"""IFG Email Drafting Agent — CLI entry point.

Modes:
  scan                                       — run all 3 scanners, draft for every hit
  scan --kind {post_meeting|stale_followup|inbound_vague}
                                              — run a single scanner
  run --fixture fixtures/inbound_vague.json   — bypass O365, run pipeline against a fixture
  run --all-fixtures                          — run all fixtures (used to regenerate outputs/)
  --verbose                                   — print intermediate state after each node
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from email_agent.config import CONFIG
from email_agent.graph import build_graph
from email_agent.state import TriggerEvent

KIND_TO_SCANNER = {
    "post_meeting": "email_agent.scanners.post_meeting",
    "stale_followup": "email_agent.scanners.stale_followup",
    "inbound_vague": "email_agent.scanners.inbound_vague",
}


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _run_pipeline(trigger: TriggerEvent, verbose: bool) -> dict:
    graph = build_graph()
    initial_state = {"trigger": trigger, "retry_count": 0}
    if verbose:
        print(f"\n=== running pipeline for {trigger.kind} (source={trigger.source_ref}) ===")
        for step in graph.stream(initial_state):
            for node_name, node_state in step.items():
                print(f"\n[{node_name}] →")
                for k, v in node_state.items():
                    preview = str(v)[:300]
                    print(f"  {k}: {preview}")
    return graph.invoke(initial_state)


def _load_fixture(path: Path) -> TriggerEvent:
    data = json.loads(path.read_text())
    return TriggerEvent(**data)


def cmd_run(args: argparse.Namespace) -> int:
    if args.all_fixtures:
        fixtures = sorted(CONFIG.fixtures_dir.glob("*.json"))
        if not fixtures:
            print(f"ERROR: no fixtures in {CONFIG.fixtures_dir}", file=sys.stderr)
            return 1
        for fx in fixtures:
            print(f"\n=== fixture: {fx.name} ===")
            trigger = _load_fixture(fx)
            result = _run_pipeline(trigger, args.verbose)
            final_draft = result.get("final_draft")
            if final_draft:
                print(final_draft.render())
        return 0

    if not args.fixture:
        print("ERROR: --fixture or --all-fixtures required", file=sys.stderr)
        return 1
    trigger = _load_fixture(Path(args.fixture))
    result = _run_pipeline(trigger, args.verbose)
    final_draft = result.get("final_draft")
    if final_draft:
        print(final_draft.render())
    else:
        print("(no draft produced)", file=sys.stderr)
        if result.get("error"):
            print(f"error: {result['error']}", file=sys.stderr)
        return 2
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    import importlib

    if args.kind:
        modules = {args.kind: KIND_TO_SCANNER[args.kind]}
    else:
        modules = KIND_TO_SCANNER

    total = 0
    for kind, module_path in modules.items():
        scanner = importlib.import_module(module_path)
        triggers = scanner.scan()
        print(f"[{kind}] {len(triggers)} trigger(s)")
        for trigger in triggers:
            result = _run_pipeline(trigger, args.verbose)
            if result.get("final_draft"):
                total += 1
                print(f"  draft created: {result.get('outlook_draft_id')}")
    print(f"\n{total} draft(s) created")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="IFG Email Drafting Agent")
    parser.add_argument("--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="run scanners against live Outlook")
    p_scan.add_argument("--kind", choices=list(KIND_TO_SCANNER.keys()))
    p_scan.set_defaults(func=cmd_scan)

    p_run = sub.add_parser("run", help="run pipeline against a fixture (offline)")
    p_run.add_argument("--fixture", type=str, help="path to a fixture JSON file")
    p_run.add_argument("--all-fixtures", action="store_true", help="run every fixture in fixtures/")
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
