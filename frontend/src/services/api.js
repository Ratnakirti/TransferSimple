import axios from 'axios'

const BASE = '/api'

// ── REST ────────────────────────────────────────────────────────────

export const api = {
  health: ()                        => axios.get(`${BASE}/health`),
  extractTest: (filename)           => axios.post(`${BASE}/extract-test`, { filename }),
  triggerSim: (simId)               => axios.post(`${BASE}/sim/${simId}`),
  getTransfer: (cardId)             => axios.get(`${BASE}/transfer/${cardId}`),
  getTransfers: ()                  => axios.get(`${BASE}/transfers`),
  clearColumn: (state)              => axios.delete(`${BASE}/transfers`, { params: { state } }),
  requeueReview: ()                 => axios.post(`${BASE}/transfers/requeue-review`),
  approve: (cardId, atonDraft, customerDraft, approvedBy = 'ops_specialist') =>
    axios.post(`${BASE}/transfer/${cardId}/approve`, {
      aton_draft:     atonDraft,
      customer_draft: customerDraft,
      approved_by:    approvedBy,
    }),
  sendAton: (cardId, draft, approvedBy = 'ops_specialist') =>
    axios.post(`${BASE}/transfer/${cardId}/send-aton`, { draft, approved_by: approvedBy }),
  sendCustomer: (cardId, draft, approvedBy = 'ops_specialist') =>
    axios.post(`${BASE}/transfer/${cardId}/send-customer`, { draft, approved_by: approvedBy }),
  reject: (cardId) => axios.post(`${BASE}/transfer/${cardId}/reject`),
  moveToReview: (cardId) => axios.post(`${BASE}/transfer/${cardId}/move-to-review`),
}

// ── WebSocket ────────────────────────────────────────────────────────

let _ws = null
let _reconnectTimer = null

export function connectWebSocket(onMessage) {
  function open() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    _ws = new WebSocket(`${protocol}//${window.location.host}/ws`)

    _ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage(data)
      } catch (_) { /* ignore malformed frames */ }
    }

    _ws.onclose = () => {
      // Reconnect after 2 s
      _reconnectTimer = setTimeout(open, 2000)
    }

    _ws.onerror = () => {
      _ws.close()
    }
  }

  open()

  return () => {
    clearTimeout(_reconnectTimer)
    _ws?.close()
  }
}
