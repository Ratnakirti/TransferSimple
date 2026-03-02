"""
REST API routes for the TransferSimple backend.

Endpoints:
  GET    /api/health                            — liveness + dependency check
  GET    /api/transfers                         — list all current cards (for page refresh)
  DELETE /api/transfers?state=<state>           — bulk-delete cards in a column
  POST   /api/transfers/requeue-review          — move all in_review cards back to incoming
  POST   /api/extract-test                      — dev tool: extract text from a bucket file
  POST   /api/sim/{sim_id}                      — trigger a simulation run (1–4)
  GET    /api/transfer/{card_id}                — get current card state
  GET    /api/transfer/{card_id}/preview-image  — raw bytes for FAX image preview
  POST   /api/transfer/{card_id}/move-to-review — user-triggered column move
  POST   /api/transfer/{card_id}/approve        — resume graph with human-approved drafts
  POST   /api/transfer/{card_id}/send-aton      — send ATON institution response independently
  POST   /api/transfer/{card_id}/send-customer  — send customer response independently
  POST   /api/transfer/{card_id}/reject         — discard a pending card
"""
import asyncio
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi.responses import Response

from app.agents.graph import transfer_graph, memory
from app.agents.nodes import GraphState
from app.api.websocket import manager
from app.models.schemas import (
    TransferCard,
    ATONMessage,
    Resolution,
    ApproveRequest,
    SendRequest,
    ExtractTestRequest,
)
from app.services.supabase_client import download_sim_file, ping
from app.services.extractor import extract_text
from app.config import FUELIX_API_KEY, BASE_URL

router = APIRouter(prefix="/api")

# ── In-memory stores (sufficient for local demo) ──────────────────────
_cards:           dict[str, TransferCard] = {}
_file_cache:      dict[str, bytes]        = {}   # card_id → raw file bytes (FAX/PDF)
_file_type_cache: dict[str, str]          = {}   # card_id → MIME type

# ── Simulation file manifest ──────────────────────────────────────────
_SIM_FILES: dict[int, list[tuple[str, str]]] = {
    1: [("sim_1_email.txt", "Email")],
    2: [("sim_2_FAX.png",   "FAX")],
    3: [("sim_3_PDF.pdf",   "PDF")],
    4: [
        ("sim_4_email.txt", "Email"),
        ("sim_4_FAX.png",   "FAX"),
        ("sim_4_PDF.pdf",   "PDF"),
    ],
}


# ── Helpers ────────────────────────────────────────────────────────────

def _pipeline_status_to_ui_state(pipeline_status: str, force_state: Optional[str] = None) -> str:
    """Map LangGraph pipeline status to the UI column state."""
    if force_state:
        return force_state
    if pipeline_status == "responded":
        return "responded"
    # incoming / aton_ready / all_ready all stay in the Incoming column
    # until the user explicitly clicks "Move to Review"
    return "incoming"


def _state_to_card(
    state: GraphState,
    force_state: Optional[str] = None,
) -> TransferCard:
    """Convert a LangGraph state snapshot to a TransferCard response model."""
    aton_data        = state.get("aton_parsed")
    customer         = state.get("customer")
    resolution       = state.get("resolution")
    pipeline_status  = state.get("status", "incoming")
    file_preview_text = state.get("file_preview_text", "")

    aton_model: Optional[ATONMessage] = None
    if aton_data:
        try:
            aton_model = ATONMessage(
                ticket_id              = aton_data.get("ticket_id", ""),
                transfer_type          = aton_data.get("transfer_type", "Transfer In"),
                rejection_codes        = aton_data.get("rejection_codes", []),
                client_name            = aton_data.get("client_name", ""),
                sin                    = aton_data.get("sin", ""),
                ws_account_num         = aton_data.get("ws_account_num", ""),
                delivering_institution = aton_data.get("delivering_institution", ""),
                receiving_institution  = aton_data.get("receiving_institution", ""),
                source_email           = aton_data.get("source_email", ""),
                source_fax             = aton_data.get("source_fax") or None,
                raw_text               = state.get("raw_text", ""),
            )
        except Exception:
            pass

    resolution_model: Optional[Resolution] = None
    if resolution:
        try:
            resolution_model = Resolution(**resolution)
        except Exception:
            pass

    ui_state = _pipeline_status_to_ui_state(pipeline_status, force_state)

    return TransferCard(
        card_id           = state["card_id"],
        input_type        = state["input_type"],
        state             = ui_state,
        pipeline_status   = pipeline_status,
        file_preview_text = file_preview_text,
        aton_message      = aton_model,
        customer          = customer,
        resolution        = resolution_model,
    )


async def _broadcast_card(card: TransferCard) -> None:
    await manager.broadcast({
        "event": "card_updated",
        "card":  card.model_dump(),
    })


async def _run_graph(card_id: str, filename: str, input_type: str) -> None:
    """
    Background task: run the LangGraph pipeline for one simulation file.
    Streams node-level updates and broadcasts after each major pipeline milestone.
    The card stays in the Incoming column until the user manually moves it to Review.
    """
    config = {"configurable": {"thread_id": card_id}}

    initial_state: GraphState = {
        "card_id":          card_id,
        "filename":         filename,
        "input_type":       input_type,
        "raw_text":         "",
        "file_preview_text": "",
        "aton_parsed":      None,
        "customer":         None,
        "resolution":       None,
        "approved_drafts":  None,
        "status":           "incoming",
    }

    # Broadcast placeholder so the card appears in Incoming immediately
    placeholder = TransferCard(
        card_id         = card_id,
        input_type      = input_type,
        state           = "incoming",
        pipeline_status = "incoming",
    )
    _cards[card_id] = placeholder
    await _broadcast_card(placeholder)

    try:
        # Stream node-level updates; graph pauses automatically before submit_node
        async for chunk in transfer_graph.astream(
            initial_state, config=config, stream_mode="updates"
        ):
            for node_name, node_output in chunk.items():
                # After ingest: cache FAX/PDF bytes for preview endpoint
                if node_name == "ingest" and input_type in ("FAX", "PDF"):
                    try:
                        raw = await download_sim_file(filename)
                        _file_cache[card_id] = raw
                        _file_type_cache[card_id] = (
                            "image/png" if input_type == "FAX" else "application/pdf"
                        )
                    except Exception:
                        pass

                # After parse: ATON fields are ready — broadcast so skeleton resolves
                if node_name == "parse":
                    snapshot = transfer_graph.get_state(config)
                    current_vals = {**snapshot.values, **node_output}
                    existing = _cards.get(card_id)
                    # Preserve in_review if user already clicked Review
                    fstate = existing.state if (existing and existing.state == "in_review") else None
                    card = _state_to_card(current_vals, force_state=fstate)
                    _cards[card_id] = card
                    await _broadcast_card(card)

                # After resolve: confidence + resolution ready — broadcast again
                if node_name == "resolve":
                    snapshot = transfer_graph.get_state(config)
                    current_vals = {**snapshot.values, **node_output}
                    existing = _cards.get(card_id)
                    fstate = existing.state if (existing and existing.state == "in_review") else None
                    card = _state_to_card(current_vals, force_state=fstate)
                    _cards[card_id] = card
                    await _broadcast_card(card)

        # Final snapshot after graph pauses at submit interrupt
        snapshot   = transfer_graph.get_state(config)
        final_vals = snapshot.values
        existing   = _cards.get(card_id)
        fstate     = existing.state if (existing and existing.state == "in_review") else None
        final_card = _state_to_card(final_vals, force_state=fstate)
        _cards[card_id] = final_card
        await _broadcast_card(final_card)

    except Exception as exc:
        await manager.broadcast({
            "event":   "card_error",
            "card_id": card_id,
            "error":   str(exc),
        })
        raise


# ── Routes ─────────────────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    supabase_ok = await ping()
    llm_ok = bool(FUELIX_API_KEY and BASE_URL)
    return {
        "status":   "ok" if (supabase_ok and llm_ok) else "degraded",
        "supabase": "connected" if supabase_ok else "unreachable",
        "llm":      "reachable" if llm_ok else "missing_api_key",
    }


@router.get("/transfers")
async def list_transfers():
    """Return all current card snapshots so clients can rehydrate on page refresh."""
    return [c.model_dump() for c in _cards.values()]


@router.delete("/transfers")
async def clear_transfers(state: str = Query(..., description="Column state to clear: incoming | responded")):
    """
    Bulk-delete all cards in the given column state.
    Broadcasts a card_removed event for each deleted card.
    """
    if state not in ("incoming", "responded"):
        raise HTTPException(status_code=400, detail="state must be 'incoming' or 'responded'")
    to_delete = [cid for cid, c in _cards.items() if c.state == state]
    for cid in to_delete:
        del _cards[cid]
        _file_cache.pop(cid, None)
        _file_type_cache.pop(cid, None)
        await manager.broadcast({"event": "card_removed", "card_id": cid})
    return {"deleted": len(to_delete)}


@router.post("/transfers/requeue-review")
async def requeue_review():
    """Move all in_review cards back to the Incoming column."""
    requeued = []
    for cid, card in list(_cards.items()):
        if card.state == "in_review":
            updated = card.model_copy(update={"state": "incoming"})
            _cards[cid] = updated
            await _broadcast_card(updated)
            requeued.append(cid)
    return {"requeued": len(requeued)}


@router.post("/extract-test")
async def extract_test(body: ExtractTestRequest):
    """Dev endpoint — download a bucket file and return its extracted text."""
    try:
        file_bytes = await download_sim_file(body.filename)
        text = extract_text(body.filename, file_bytes)
        return {"filename": body.filename, "extracted_text": text, "char_count": len(text)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/sim/{sim_id}")
async def trigger_sim(sim_id: int, background_tasks: BackgroundTasks):
    """Trigger a simulation run. SIM 4 starts 3 concurrent graph runs."""
    if sim_id not in _SIM_FILES:
        raise HTTPException(status_code=400, detail=f"sim_id must be 1–4, got {sim_id}")

    files    = _SIM_FILES[sim_id]
    card_ids = []

    for filename, input_type in files:
        card_id = str(uuid.uuid4())
        card_ids.append(card_id)
        background_tasks.add_task(_run_graph, card_id, filename, input_type)

    return {"sim_id": sim_id, "card_ids": card_ids}


@router.get("/transfer/{card_id}")
async def get_transfer(card_id: str):
    """Return the current card snapshot."""
    card = _cards.get(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card.model_dump()


@router.get("/transfer/{card_id}/preview-image")
async def preview_image(card_id: str):
    """Return the raw FAX/PDF bytes for the preview panel in the modal."""
    data = _file_cache.get(card_id)
    if not data:
        raise HTTPException(status_code=404, detail="No preview available for this card")
    mime = _file_type_cache.get(card_id, "application/octet-stream")
    return Response(content=data, media_type=mime)


@router.post("/transfer/{card_id}/move-to-review")
async def move_to_review(card_id: str):
    """
    User-triggered action: move an Incoming card to the In-Review column.
    Only allowed once the pipeline has at least reached aton_ready status.
    """
    card = _cards.get(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    if card.pipeline_status == "incoming":
        raise HTTPException(
            status_code=409,
            detail="Card extraction not yet complete. Wait for ATON fields to load.",
        )

    updated = card.model_copy(update={"state": "in_review"})
    _cards[card_id] = updated
    await _broadcast_card(updated)
    return {"card_id": card_id, "state": "in_review"}


@router.post("/transfer/{card_id}/approve")
async def approve_transfer(card_id: str, body: ApproveRequest):
    """
    Resume the paused LangGraph graph with the specialist's approved drafts.
    The graph will run submit_node, log the audit, and mark the card as responded.
    """
    card = _cards.get(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    config = {"configurable": {"thread_id": card_id}}

    transfer_graph.update_state(config, {
        "approved_drafts": {
            "aton":        body.aton_draft,
            "customer":    body.customer_draft,
            "approved_by": body.approved_by,
        },
        "status": "responded",
    })

    # Resume — runs submit_node → END
    await transfer_graph.ainvoke(None, config=config)

    snapshot   = transfer_graph.get_state(config)
    final_card = _state_to_card(snapshot.values)
    _cards[card_id] = final_card
    await _broadcast_card(final_card)

    return final_card.model_dump()


@router.post("/transfer/{card_id}/send-aton")
async def send_aton(card_id: str, body: SendRequest):
    """Send the ATON institution response independently. Moves card to responded."""
    card = _cards.get(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    current_res = card.resolution.model_dump() if card.resolution else {}
    current_res.update({"aton_sent": True, "aton_response_draft": body.draft, "status": "sent"})
    updated = card.model_copy(update={
        "state":      "responded",
        "resolution": Resolution(**current_res),
    })
    _cards[card_id] = updated
    await _broadcast_card(updated)
    return updated.model_dump()


@router.post("/transfer/{card_id}/send-customer")
async def send_customer(card_id: str, body: SendRequest):
    """Send the customer response independently. Moves card to responded."""
    card = _cards.get(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    current_res = card.resolution.model_dump() if card.resolution else {}
    current_res.update({"customer_sent": True, "customer_response_draft": body.draft, "status": "sent"})
    updated = card.model_copy(update={
        "state":      "responded",
        "resolution": Resolution(**current_res),
    })
    _cards[card_id] = updated
    await _broadcast_card(updated)
    return updated.model_dump()


@router.post("/transfer/{card_id}/reject")
async def reject_transfer(card_id: str):
    """Discard a pending card without submitting. Moves it back to in_review."""
    card = _cards.get(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    updated = card.model_copy(update={"state": "in_review"})
    _cards[card_id] = updated
    await _broadcast_card(updated)
    return {"card_id": card_id, "state": "in_review"}
