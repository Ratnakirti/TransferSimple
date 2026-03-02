import { defineStore } from 'pinia'
import { ref, computed, onUnmounted } from 'vue'
import { connectWebSocket } from '../services/api'

export const useTransferStore = defineStore('transfers', () => {
  // ── State ──────────────────────────────────────────────────────────
  const cards = ref({})   // card_id → card object

  // ── Derived column views ───────────────────────────────────────────
  const incoming  = computed(() => Object.values(cards.value).filter(c => c.state === 'incoming'))
  const inReview  = computed(() => Object.values(cards.value).filter(c => c.state === 'in_review'))
  const responded = computed(() => Object.values(cards.value).filter(c => c.state === 'responded'))

  // ── Actions ────────────────────────────────────────────────────────
  function upsertCard(card) {
    cards.value[card.card_id] = card
  }

  function moveCard(cardId, newState) {
    if (cards.value[cardId]) {
      cards.value[cardId] = { ...cards.value[cardId], state: newState }
    }
  }

  function removeCard(cardId) {
    delete cards.value[cardId]
  }

  function clearColumnLocally(state) {
    for (const cid of Object.keys(cards.value)) {
      if (cards.value[cid].state === state) delete cards.value[cid]
    }
  }

  // ── WebSocket listener ─────────────────────────────────────────────
  let _disconnect = null

  function startListening() {
    _disconnect = connectWebSocket((message) => {
      if (message.event === 'card_updated' && message.card) {
        upsertCard(message.card)
      } else if (message.event === 'new_card' && message.card) {
        upsertCard(message.card)
      } else if (message.event === 'card_removed' && message.card_id) {
        removeCard(message.card_id)
      } else if (message.event === 'card_error') {
        if (message.card_id) removeCard(message.card_id)
        // Emit a custom DOM event so App.vue can show a toast with the error
        window.dispatchEvent(new CustomEvent('card-pipeline-error', {
          detail: { error: message.error || 'Pipeline failed — check server logs.' }
        }))
      }
    })
  }

  function stopListening() {
    _disconnect?.()
  }

  return {
    cards,
    incoming,
    inReview,
    responded,
    upsertCard,
    moveCard,
    removeCard,
    clearColumnLocally,
    startListening,
    stopListening,
  }
})
