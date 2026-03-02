"""
Pydantic data models shared across the backend.
"""
from typing import Literal, Optional
from pydantic import BaseModel


class ATONMessage(BaseModel):
    ticket_id:              str
    transfer_type:          Literal["Transfer In", "Transfer Out"]
    rejection_codes:        list[str]
    client_name:            str
    sin:                    str
    ws_account_num:         str
    delivering_institution: str
    receiving_institution:  str
    source_email:           str                    # email of sending institution
    source_fax:             Optional[str] = None   # fax number (FAX-type inputs only)
    raw_text:               str          # full extracted text (for reference)


class Resolution(BaseModel):
    aton_response_draft:     str
    customer_response_draft: str
    confidence_score:        float        # 0.0 – 1.0; see rejection_codes.py
    reasoning:               Optional[str] = None  # deprecated — no longer populated
    status: Literal["pending", "approved", "sent"] = "pending"
    aton_sent:               bool = False  # True once ATON institution response is sent
    customer_sent:           bool = False  # True once customer response is sent


class TransferCard(BaseModel):
    card_id:           str
    input_type:        Literal["Email", "FAX", "PDF"]
    state:             Literal["incoming", "in_review", "responded"] = "incoming"
    pipeline_status:   str = "incoming"   # tracks backend progress ("aton_ready", "all_ready", etc.)
    aton_message:      Optional[ATONMessage] = None
    customer:          Optional[dict]        = None
    resolution:        Optional[Resolution]  = None
    file_preview_text: str = ""             # first ~800 chars of extracted text for Incoming panel


# ── Request bodies ────────────────────────────────────────────────────

class ExtractTestRequest(BaseModel):
    filename: str


class ApproveRequest(BaseModel):
    """Payload sent when a specialist approves (and optionally edits) the AI drafts."""
    aton_draft:     str
    customer_draft: str
    approved_by:    str = "ops_specialist"


class SendRequest(BaseModel):
    """Payload for sending a single response (aton or customer) independently."""
    draft:       str
    approved_by: str = "ops_specialist"
