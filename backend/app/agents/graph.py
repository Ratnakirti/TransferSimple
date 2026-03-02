"""
LangGraph state machine for the TransferSimple AI pipeline.

Flow:
  ingest_node → parse_node → lookup_node → resolve_node
  ══ INTERRUPT before submit_node (human review) ══
  submit_node → END

The MemorySaver checkpointer persists state across the interrupt
so routes can resume a paused graph using the same thread_id (card_id).
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.nodes import (
    GraphState,
    ingest_node,
    parse_node,
    lookup_node,
    resolve_node,
    submit_node,
)

# ── Build the graph ────────────────────────────────────────────────────

_builder = StateGraph(GraphState)

_builder.add_node("ingest",  ingest_node)
_builder.add_node("parse",   parse_node)
_builder.add_node("lookup",  lookup_node)
_builder.add_node("resolve", resolve_node)
_builder.add_node("submit",  submit_node)

_builder.set_entry_point("ingest")

_builder.add_edge("ingest",  "parse")
_builder.add_edge("parse",   "lookup")
_builder.add_edge("lookup",  "resolve")
_builder.add_edge("resolve", "submit")
_builder.add_edge("submit",  END)

# ── Shared in-memory checkpointer ─────────────────────────────────────
# One MemorySaver instance shared across all graph runs.
# thread_id = card_id  →  each transfer card gets its own isolated state.
memory = MemorySaver()

# ── Compile  ───────────────────────────────────────────────────────────
# interrupt_before=["submit"] ensures the graph pauses AFTER resolve_node
# completes (i.e. AI drafts are ready) and BEFORE submit_node runs
# (the irreversible audit-log + status change).
transfer_graph = _builder.compile(
    checkpointer=memory,
    interrupt_before=["submit"],
)
