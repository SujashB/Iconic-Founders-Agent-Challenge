"""LangGraph StateGraph wiring for the email-drafting pipeline."""
from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, StateGraph

from email_agent.nodes import (
    classifier,
    context_extractor,
    critic,
    draft_writer,
    drafter,
    sentiment,
    strategy,
    trigger_router,
)
from email_agent.state import EmailDraftState


@lru_cache(maxsize=1)
def build_graph():
    g = StateGraph(EmailDraftState)

    g.add_node("trigger_router", trigger_router.trigger_router)
    g.add_node("classifier", classifier.classify)
    g.add_node("context_extractor", context_extractor.extract_context)
    g.add_node("sentiment", sentiment.analyze)
    g.add_node("strategy", strategy.select_strategy)
    g.add_node("drafter", drafter.draft)
    g.add_node("critic", critic.critique)
    g.add_node("draft_writer", draft_writer.write)
    g.add_node("drop", lambda state: {"error": "classifier dropped event"})

    g.set_entry_point("trigger_router")
    g.add_conditional_edges(
        "trigger_router",
        trigger_router.needs_classifier,
        {"classifier": "classifier", "context_extractor": "context_extractor"},
    )
    g.add_conditional_edges(
        "classifier",
        classifier.classifier_decision,
        {"context_extractor": "context_extractor", "drop": "drop"},
    )
    g.add_edge("context_extractor", "sentiment")
    g.add_edge("sentiment", "strategy")
    g.add_edge("strategy", "drafter")
    g.add_edge("drafter", "critic")
    g.add_conditional_edges(
        "critic",
        critic.critic_decision,
        {"drafter": "drafter", "draft_writer": "draft_writer"},
    )
    g.add_edge("draft_writer", END)
    g.add_edge("drop", END)

    return g.compile()
