"""
LangGraph node functions for the TransferSimple AI pipeline.

Graph flow:
  ingest_node → parse_node → lookup_node → resolve_node
  [interrupt before submit_node — human review happens here]
  submit_node

Each node is an async function that receives and returns GraphState.
"""
import json
import logging
import re
from typing import Optional, TypedDict

import httpx

log = logging.getLogger(__name__)

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from app.config import FUELIX_API_KEY, BASE_URL, MODEL_NAME, GOOGLE_API_KEY, GOOGLE_BASE_URL, GOOGLE_MODEL, LLM_PROVIDER, PROXY
from app.services.extractor import extract_text
from app.services.supabase_client import download_sim_file, get_customer_by_ws_account, log_audit
from app.services.rejection_codes import (
    get_code_description,
    compute_confidence,
)
from app.agents.prompts import PARSE_ATON_PROMPT, RESOLUTION_PROMPT


# ── Shared LLM instance (module-level singleton) ──────────────────────

def _build_llm() -> ChatOpenAI:
    if LLM_PROVIDER == "google":
        # Google AI Studio — still requires the corporate proxy for outbound HTTPS.
        # max_tokens is set high because Gemini 2.5 Flash is a thinking model:
        # the <think>...</think> tokens count against the budget before the JSON.
        return ChatOpenAI(
            model=GOOGLE_MODEL,
            api_key=GOOGLE_API_KEY,
            base_url=GOOGLE_BASE_URL,
            temperature=0.1,
            max_tokens=16384,
            http_async_client=httpx.AsyncClient(proxy=PROXY, trust_env=False),
        )
    # Default: Fuelix — route through corporate proxy explicitly.
    return ChatOpenAI(
        model=MODEL_NAME,
        api_key=FUELIX_API_KEY,
        base_url=BASE_URL,
        temperature=0.1,
        max_tokens=16384,
        http_async_client=httpx.AsyncClient(proxy=PROXY, trust_env=False),
    )


_llm: Optional[ChatOpenAI] = None


def get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = _build_llm()
    return _llm


# ── Graph state ───────────────────────────────────────────────────────

class GraphState(TypedDict):
    card_id:           str
    filename:          str
    input_type:        str              # "Email" | "FAX" | "PDF"
    raw_text:          str
    file_preview_text: str              # first ~700 chars for text/pdf; empty for images
    aton_parsed:       Optional[dict]   # fields from PARSE_ATON_PROMPT
    customer:          Optional[dict]   # row from customers table
    resolution:        Optional[dict]   # drafts + confidence from RESOLUTION_PROMPT
    approved_drafts:   Optional[dict]   # human-edited final drafts {"aton": ..., "customer": ...}
    status:            str              # pipeline: "incoming" | "aton_ready" | "all_ready" | "responded"


# ── Node helpers ──────────────────────────────────────────────────────

def _extract_draft_fields(text: str) -> Optional[dict]:
    """Regex fallback: pull aton/customer draft values from truncated or malformed JSON.

    The pattern `(?:[^"\\]|\\.)*` matches JSON string content including
    backslash-escaped sequences (\\n, \\\", etc.) but stops at an unescaped
    quote.  Works even when the closing quote / brace is missing (truncated).
    """
    def _field(key: str, src: str) -> str:
        m = re.search(
            rf'"{re.escape(key)}"\s*:\s*"((?:[^"\\]|\\.)*)',
            src,
            re.DOTALL,
        )
        return m.group(1) if m else ""

    aton     = _field("aton_response_draft",     text)
    customer = _field("customer_response_draft", text)
    if aton or customer:
        return {"aton_response_draft": aton, "customer_response_draft": customer}
    return None


def _clean_llm_json(text: str) -> str:
    """Extract and clean a JSON object from LLM output.

    Handles:
    - Markdown code fences (```json ... ```)
    - Thinking model preambles (<think>...</think>, reasoning tokens, etc.)
    - Literal newlines / carriage-returns inside JSON string values
    """
    text = text.strip()

    # Strip <think>...</think> blocks (Gemini / o1-style thinking tokens)
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()

    # Remove ```json ... ``` or ``` ... ``` fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # If there is extraneous text before/after the JSON object, extract just
    # the outermost { ... } block so stray prose doesn't break json.loads.
    brace_start = text.find("{")
    brace_end   = text.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        text = text[brace_start : brace_end + 1]

    # Walk char-by-char and escape bare newlines/carriage-returns inside strings
    result: list[str] = []
    in_string   = False
    escape_next = False
    for ch in text:
        if escape_next:
            result.append(ch)
            escape_next = False
        elif ch == "\\" and in_string:
            result.append(ch)
            escape_next = True
        elif ch == '"':
            result.append(ch)
            in_string = not in_string
        elif in_string and ch == "\n":
            result.append("\\n")
        elif in_string and ch == "\r":
            result.append("\\r")
        else:
            result.append(ch)
    return "".join(result)


# ── Nodes ─────────────────────────────────────────────────────────────

async def ingest_node(state: GraphState) -> GraphState:
    """Download the source file from Supabase bucket and extract text."""
    file_bytes = await download_sim_file(state["filename"])
    raw_text   = extract_text(state["filename"], file_bytes)
    # Store a text preview for the Incoming card right panel (up to 4000 chars)
    file_preview_text = raw_text[:4000] if raw_text else ""
    return {**state, "raw_text": raw_text, "file_preview_text": file_preview_text, "status": "incoming"}


async def parse_node(state: GraphState) -> GraphState:
    """Call LLM to extract structured ATON fields from raw text."""
    # Escape any literal { } in the OCR/extracted text so Python's .format()
    # doesn't treat them as template placeholders and raise KeyError.
    safe_raw = state["raw_text"].replace("{", "{{").replace("}", "}}")
    prompt  = PARSE_ATON_PROMPT.format(raw_text=safe_raw)
    message = HumanMessage(content=prompt)
    response = await get_llm().ainvoke([message])
    raw_json = _clean_llm_json(response.content)

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        # Fallback: return minimal parsed dict so the pipeline doesn't crash
        parsed = {
            "ticket_id": "UNKNOWN",
            "transfer_type": "Transfer In",
            "rejection_codes": [],
            "client_name": "Unknown",
            "sin": "",
            "ws_account_num": "",
            "delivering_institution": "Unknown",
            "receiving_institution": "Wealthsimple",
            "source_email": "",
            "source_fax": "",
        }

    return {**state, "aton_parsed": parsed, "status": "aton_ready"}


async def lookup_node(state: GraphState) -> GraphState:
    """Fetch the matching Wealthsimple customer record from Supabase."""
    ws_account_num = (state.get("aton_parsed") or {}).get("ws_account_num", "")
    customer = None
    if ws_account_num:
        customer = await get_customer_by_ws_account(ws_account_num)
    return {**state, "customer": customer}


def _build_customer_summary(customer: Optional[dict]) -> str:
    """Format customer data into a concise string for the LLM resolution prompt."""
    if not customer:
        return "No matching Wealthsimple customer found for provided account number."

    accounts = customer.get("accounts", {})
    account_lines = []

    if accounts.get("hasChequing"):
        chq = accounts.get("chequing") or {}
        account_lines.append(f"  • Chequing: ${chq.get('value_CAD', 0):,.2f} CAD")

    if accounts.get("hasNonRegistered"):
        nr = accounts.get("nonRegistered") or {}
        account_lines.append(f"  • Non-Registered: ${nr.get('value_CAD', 0):,.2f} CAD")

    if accounts.get("hasRegistered"):
        reg = accounts.get("registered") or {}
        if reg.get("hasRRSP"):
            rrsp = reg.get("RRSP") or {}
            account_lines.append(f"  • RRSP: ${rrsp.get('value_CAD', 0):,.2f} CAD")
        if reg.get("hasTFSA"):
            tfsa = reg.get("TFSA") or {}
            holdings = tfsa.get("holdings", [])
            tickers = ", ".join(h["ticker"] for h in holdings)
            account_lines.append(f"  • TFSA holdings: {tickers}")
        if reg.get("hasFHSA"):
            fhsa = reg.get("FHSA") or {}
            account_lines.append(f"  • FHSA: ${fhsa.get('value_CAD', 0):,.2f} CAD")

    accounts_text = "\n".join(account_lines) if account_lines else "  (no account details)"

    # Build "does not hold" list so the LLM can reason about missing account types
    missing = []
    if not accounts.get("hasChequing"):
        missing.append("Chequing")
    if not accounts.get("hasNonRegistered"):
        missing.append("Non-Registered")
    reg = accounts.get("registered") or {}
    if not reg.get("hasRRSP"):
        missing.append("RRSP")
    if not reg.get("hasTFSA"):
        missing.append("TFSA")
    if not reg.get("hasFHSA"):
        missing.append("FHSA")
    missing_text = ", ".join(missing) if missing else "none"

    return (
        f"Name on file: {customer.get('first_name', '')} {customer.get('last_name', '')}\n"
        f"Email: {customer.get('email', '')}\n"
        f"WS Account: {customer.get('ws_account_num', '')}\n"
        f"Accounts held:\n{accounts_text}\n"
        f"Account types NOT held at Wealthsimple: {missing_text}"
    )


async def resolve_node(state: GraphState) -> GraphState:
    """Call LLM to draft resolution messages and compute confidence score."""
    parsed   = state.get("aton_parsed") or {}
    codes    = parsed.get("rejection_codes", [])
    customer = state.get("customer")

    # Build rejection code detail block
    code_lines = []
    for code in codes:
        desc = get_code_description(code)
        code_lines.append(f"  • {code}: {desc}")
    rejection_codes_detail = "\n".join(code_lines) if code_lines else "  (no rejection codes found)"

    customer_summary = _build_customer_summary(customer)

    def _sf(v: str) -> str:
        """Escape braces in a format-string value to prevent KeyError."""
        return str(v).replace("{", "{{").replace("}", "}}")

    prompt = RESOLUTION_PROMPT.format(
        ticket_id=_sf(parsed.get("ticket_id", "UNKNOWN")),
        transfer_type=_sf(parsed.get("transfer_type", "Transfer In")),
        delivering_institution=_sf(parsed.get("delivering_institution", "Unknown")),
        receiving_institution=_sf(parsed.get("receiving_institution", "Wealthsimple")),
        client_name=_sf(parsed.get("client_name", "Unknown")),
        sin=_sf(parsed.get("sin", "")),
        ws_account_num=_sf(parsed.get("ws_account_num", "")),
        rejection_codes_detail=_sf(rejection_codes_detail),
        ws_customer_summary=_sf(customer_summary),
    )

    message  = HumanMessage(content=prompt)
    response = await get_llm().ainvoke([message])
    raw_json = _clean_llm_json(response.content)

    try:
        llm_result = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        log.error(
            "resolve_node: JSON parse failed (%s).\n"
            "--- raw LLM output (first 1000 chars) ---\n%s\n"
            "--- cleaned (first 1000 chars) ---\n%s",
            exc, response.content[:1000], raw_json[:1000],
        )
        # Attempt regex extraction — recovers partial drafts from truncated output.
        llm_result = _extract_draft_fields(raw_json) or _extract_draft_fields(response.content)
        if llm_result:
            log.warning("resolve_node: recovered partial drafts via regex fallback.")
        else:
            llm_result = {
                "aton_response_draft":     "Unable to generate draft — please review manually.",
                "customer_response_draft": "Unable to generate draft — please review manually.",
            }

    confidence = compute_confidence(codes)

    resolution = {
        "aton_response_draft":     llm_result.get("aton_response_draft", ""),
        "customer_response_draft": llm_result.get("customer_response_draft", ""),
        "confidence_score":        confidence,
        "status":                  "pending",
    }

    # Keep status "all_ready" — the UI column move to "in_review" is user-triggered
    return {**state, "resolution": resolution, "status": "all_ready"}


async def submit_node(state: GraphState) -> GraphState:
    """
    Log the approved transfer to the audit table and mark as responded.
    The `approved_drafts` field is injected by the approve endpoint before
    the graph is resumed — it contains the final (possibly human-edited) texts.
    """
    approved = state.get("approved_drafts") or {}
    parsed   = state.get("aton_parsed") or {}

    await log_audit({
        "ticket_id":          parsed.get("ticket_id", "UNKNOWN"),
        "card_id":            state["card_id"],
        "action":             "approved",
        "aton_draft_sent":    approved.get("aton", ""),
        "customer_draft_sent": approved.get("customer", ""),
        "approved_by":        approved.get("approved_by", "ops_specialist"),
    })

    # Update the resolution status to "sent"
    resolution = {**(state.get("resolution") or {}), "status": "sent"}
    return {**state, "resolution": resolution, "status": "responded"}
