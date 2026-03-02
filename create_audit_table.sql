-- Run once in Supabase SQL Editor (Dashboard → SQL Editor → New query → paste → Run)
-- Creates the audit log table used by the TransferSimple backend on every approval.

CREATE TABLE IF NOT EXISTS public.transfer_audit (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id           TEXT        NOT NULL,
    card_id             TEXT        NOT NULL,
    action              TEXT        NOT NULL,              -- 'approved' | 'rejected'
    aton_draft_sent     TEXT,
    customer_draft_sent TEXT,
    approved_by         TEXT        NOT NULL DEFAULT 'ops_specialist',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for lookup by ticket
CREATE INDEX IF NOT EXISTS idx_transfer_audit_ticket_id
    ON public.transfer_audit (ticket_id);

-- Index for lookup by card
CREATE INDEX IF NOT EXISTS idx_transfer_audit_card_id
    ON public.transfer_audit (card_id);
