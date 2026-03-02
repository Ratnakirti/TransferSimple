<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="card" class="modal-backdrop" @mousedown.self="handleBackdropClick">
        <div class="modal">
          <!-- ── Header ─────────────────────────────────── -->
          <div class="modal__header">
            <div class="modal__header-left">
              <span class="text-mono font-semibold">
                {{ card.aton_message?.ticket_id ?? card.card_id }}
              </span>
              <span :class="['chip', typeChipClass]">{{ card.input_type }}</span>
              <span v-if="card.aton_message" :class="['chip', dirChipClass]">
                {{ dirArrow }} {{ card.aton_message?.transfer_type }}
              </span>
              <span v-if="card.state === 'incoming' && pipelineLabel" class="pipeline-badge">
                {{ pipelineLabel }}
              </span>
            </div>
            <!-- Confidence centred in header for in-review/responded -->
            <span
              v-if="card.state !== 'incoming' && card.resolution"
              class="modal__header-confidence"
              :style="{ color: confidenceLabelColor, background: confidenceBg, borderColor: confidenceLabelColor }"
            >
              {{ Math.round((card.resolution.confidence_score ?? 0) * 100) }}% AI Confidence
            </span>
            <button class="modal__close btn btn--ghost btn--sm" @click="$emit('close')">✕</button>
          </div>

          <!-- ── INCOMING: 2-column extract + preview ──── -->
          <template v-if="card.state === 'incoming'">
            <div class="modal__incoming">
              <!-- Left: ATON extracted fields / skeleton -->
              <div class="modal__panel">
                <h3 class="modal__panel-title">Extracted ATON Fields</h3>
                <template v-if="isExtracting">
                  <div class="skeleton-grid">
                    <div v-for="i in 8" :key="i" class="skeleton-row">
                      <div class="skeleton skeleton--label" />
                      <div class="skeleton skeleton--value" :style="{ width: (40 + i * 7) + '%' }" />
                    </div>
                  </div>
                </template>
                <template v-else>
                  <dl class="info-grid">
                    <dt>Ticket ID</dt>
                    <dd class="text-mono">{{ card.aton_message?.ticket_id ?? '—' }}</dd>

                    <dt>Transfer Type</dt>
                    <dd>{{ card.aton_message?.transfer_type ?? '—' }}</dd>

                    <dt>Client Name</dt>
                    <dd>{{ card.aton_message?.client_name ?? '—' }}</dd>

                    <dt>SIN</dt>
                    <dd class="text-mono">{{ formatSin(card.aton_message?.sin) }}</dd>

                    <dt>WS Account</dt>
                    <dd class="text-mono">{{ card.aton_message?.ws_account_num ?? '—' }}</dd>

                    <dt>Delivering</dt>
                    <dd>{{ card.aton_message?.delivering_institution ?? '—' }}</dd>

                    <dt>Receiving</dt>
                    <dd>{{ card.aton_message?.receiving_institution ?? '—' }}</dd>

                    <dt>{{ card.input_type === 'FAX' ? 'Source Fax' : 'Source Email' }}</dt>
                    <dd class="text-xs">{{ card.input_type === 'FAX' ? (card.aton_message?.source_fax || card.aton_message?.source_email || '—') : (card.aton_message?.source_email ?? '—') }}</dd>
                  </dl>
                  <div v-if="card.aton_message?.rejection_codes?.length" class="modal__codes" style="margin-top:14px">
                    <p class="text-xs text-muted" style="margin-bottom:6px">Rejection Codes</p>
                    <div v-for="code in card.aton_message.rejection_codes" :key="code" class="rejection-code">
                      <span class="rejection-code__badge chip chip--code">{{ code }}</span>
                      <span class="rejection-code__desc text-xs text-secondary">{{ codeDesc(code) }}</span>
                      <span class="rejection-code__match">Match Found!</span>
                    </div>
                  </div>
                </template>
              </div>

              <!-- Right: source document preview -->
              <div class="modal__panel modal__panel--preview">
                <h3 class="modal__panel-title">Source Document</h3>

                <!-- FAX: show spinner until backend has cached the file and image loads -->
                <template v-if="card.input_type === 'FAX'">
                  <!-- Spinner: while pipeline is still ingesting OR while img is loading -->
                  <div
                    v-if="card.pipeline_status === 'incoming' || (!faxImageLoaded && !faxImageError)"
                    class="preview-loading"
                  >
                    <span class="spinner" />
                    <span class="text-xs text-muted">Loading FAX document…</span>
                  </div>
                  <!-- Error fallback -->
                  <div v-else-if="faxImageError" class="text-muted text-sm" style="padding-top:12px">
                    FAX document could not be loaded.
                  </div>
                  <!-- Only mount img once backend has cached the file -->
                  <img
                    v-if="card.pipeline_status !== 'incoming'"
                    :key="faxImageKey"
                    :src="previewImageUrl"
                    class="preview-img"
                    :class="{ 'preview-img--hidden': !faxImageLoaded }"
                    alt="FAX document"
                    @load="faxImageLoaded = true"
                    @error="onFaxError"
                  />
                </template>

                <!-- PDF: native browser embed (only after file is cached) -->
                <template v-else-if="card.input_type === 'PDF'">
                  <div v-if="card.pipeline_status === 'incoming' || !card.pipeline_status" class="preview-loading">
                    <span class="spinner" />
                    <span class="text-xs text-muted">Loading PDF document…</span>
                  </div>
                  <embed
                    v-else
                    :src="previewImageUrl"
                    type="application/pdf"
                    class="preview-pdf"
                  />
                </template>

                <!-- Email / text: formatted with bold labels, scrollable -->
                <div v-else-if="emailLines.length" class="preview-email">
                  <p v-for="(line, i) in emailLines" :key="i" class="preview-email__line">
                    <template v-if="line.label !== null">
                      <strong class="preview-email__label">{{ line.label }}</strong>
                      <span class="preview-email__rest">{{ line.rest }}</span>
                    </template>
                    <template v-else>
                      <span class="preview-email__rest">{{ line.rest }}</span>
                    </template>
                  </p>
                </div>

                <div v-else class="text-muted text-sm" style="padding-top:12px">Loading document preview…</div>
              </div>
            </div>

            <!-- Footer: status + Move to Review button -->
            <div class="modal__incoming-footer">
              <span v-if="card.pipeline_status === 'incoming'" class="text-xs text-muted incoming-status">
                <span class="spinner" /> Extracting ATON fields…
              </span>
              <span v-else-if="card.pipeline_status === 'aton_ready'" class="text-xs text-muted">
                ATON fields ready · AI resolution in progress…
              </span>
              <span v-else class="text-xs text-muted">Ready for review</span>

              <button
                :class="['btn', card.pipeline_status === 'all_ready' ? 'btn--primary' : 'btn--ghost', 'btn--review']"
                :disabled="card.pipeline_status !== 'all_ready'"
                @click="moveToReview"
              >
                Review →
              </button>
            </div>
          </template>

          <!-- ── IN-REVIEW / RESPONDED: 4-quadrant view ─── -->
          <template v-else>
            <div class="modal__reviews">
              <!-- ── Top row: ATON info + Customer info ────── -->
              <div class="modal__top">
              <!-- Top-left: ATON message details -->
              <div class="modal__panel modal__panel--aton">
                <h3 class="modal__panel-title">ATON Message</h3>
                <dl class="info-grid info-grid--wide">
                  <dt>Ticket ID</dt>
                  <dd class="text-mono">{{ card.aton_message?.ticket_id ?? '—' }}</dd>

                  <dt>Transfer Type</dt>
                  <dd>{{ card.aton_message?.transfer_type ?? '—' }}</dd>

                  <dt>Client Name</dt>
                  <dd>{{ card.aton_message?.client_name ?? '—' }}</dd>

                  <dt>SIN</dt>
                  <dd class="text-mono">{{ formatSin(card.aton_message?.sin) }}</dd>

                  <dt>WS Account</dt>
                  <dd class="text-mono">{{ card.aton_message?.ws_account_num ?? '—' }}</dd>

                  <dt>Delivering</dt>
                  <dd>{{ card.aton_message?.delivering_institution ?? '—' }}</dd>

                  <dt>Receiving</dt>
                  <dd>{{ card.aton_message?.receiving_institution ?? '—' }}</dd>

                  <dt>{{ card.input_type === 'FAX' ? 'Source Fax' : 'Source Email' }}</dt>
                  <dd class="text-xs">{{ card.input_type === 'FAX' ? (card.aton_message?.source_fax || card.aton_message?.source_email || '—') : (card.aton_message?.source_email ?? '—') }}</dd>
                </dl>

                <!-- Rejection codes -->
                <div v-if="card.aton_message?.rejection_codes?.length" class="modal__codes">
                  <p class="text-xs text-muted" style="margin-bottom:6px">Rejection Codes</p>
                  <div
                    v-for="code in card.aton_message.rejection_codes"
                    :key="code"
                    class="rejection-code"
                  >
                    <span class="rejection-code__badge chip chip--code">{{ code }}</span>
                    <span class="rejection-code__desc text-xs text-secondary">{{ codeDesc(code) }}</span>
                    <span class="rejection-code__match">Match Found!</span>
                  </div>
                </div>
              </div>

              <!-- Top-right: Wealthsimple customer -->
              <div class="modal__panel modal__panel--customer">
                <h3 class="modal__panel-title">Wealthsimple Customer</h3>

                <template v-if="card.customer">
                  <dl class="info-grid info-grid--wide">
                    <dt>Name on File</dt>
                    <dd>{{ card.customer.first_name }} {{ card.customer.last_name }}</dd>

                    <dt>Email</dt>
                    <dd class="text-xs">{{ card.customer.email }}</dd>

                    <dt>WS Account</dt>
                    <dd class="text-mono">{{ card.customer.ws_account_num }}</dd>

                    <dt>SIN</dt>
                    <dd class="text-mono">{{ formatSin(card.customer.sin) }}</dd>
                  </dl>

                  <div class="divider" />

                  <!-- Account summary: holds + does not hold -->
                  <div class="accounts-row">
                    <div>
                      <p class="text-xs text-muted" style="margin-bottom:6px">Holds</p>
                      <div class="account-chips">
                        <span v-if="card.customer.accounts?.hasChequing"         class="chip chip--in">Chequing</span>
                        <span v-if="card.customer.accounts?.hasNonRegistered"    class="chip chip--in">Non-Reg.</span>
                        <span v-if="card.customer.accounts?.registered?.hasRRSP" class="chip chip--in">RRSP</span>
                        <span v-if="card.customer.accounts?.registered?.hasTFSA" class="chip chip--in">TFSA</span>
                        <span v-if="card.customer.accounts?.registered?.hasFHSA" class="chip chip--in">FHSA</span>
                        <span
                          v-if="!card.customer.accounts?.hasChequing && !card.customer.accounts?.hasNonRegistered && !card.customer.accounts?.registered?.hasRRSP && !card.customer.accounts?.registered?.hasTFSA && !card.customer.accounts?.registered?.hasFHSA"
                          class="text-xs text-muted"
                        >None</span>
                      </div>
                    </div>
                    <div>
                      <p class="text-xs text-muted" style="margin-bottom:6px">Does not hold</p>
                      <div class="account-chips">
                        <span v-if="!card.customer.accounts?.hasChequing"         class="chip chip--missing">Chequing</span>
                        <span v-if="!card.customer.accounts?.hasNonRegistered"    class="chip chip--missing">Non-Reg.</span>
                        <span v-if="!card.customer.accounts?.registered?.hasRRSP" class="chip chip--missing">RRSP</span>
                        <span v-if="!card.customer.accounts?.registered?.hasTFSA" class="chip chip--missing">TFSA</span>
                        <span v-if="!card.customer.accounts?.registered?.hasFHSA" class="chip chip--missing">FHSA</span>
                      </div>
                    </div>
                  </div>

                  <!-- TFSA Holdings if present -->
                  <template v-if="card.customer.accounts?.registered?.TFSA?.holdings?.length">
                    <p class="text-xs text-muted" style="margin-top:10px;margin-bottom:6px">TFSA Holdings</p>
                    <div class="holdings">
                      <span
                        v-for="h in card.customer.accounts.registered.TFSA.holdings"
                        :key="h.ticker"
                        class="holding"
                      >
                        <span class="text-mono text-xs">{{ h.ticker }}</span>
                        <span class="text-xs text-muted">{{ h.units }} units</span>
                      </span>
                    </div>
                  </template>
                </template>

                <div v-else class="text-secondary text-sm" style="padding-top:12px">
                  No matching customer found
                </div>
              </div>
            </div>

            <!-- ── Bottom row: Draft responses ────────────── -->
            <div class="modal__bottom">
              <!-- Bottom-left: ATON institution response -->
              <div class="modal__response">
                <div class="modal__response-header">
                  <h3 class="modal__panel-title">Response to ATON Institution</h3>
                  <div class="modal__response-actions">
                    <button
                      v-if="!card.resolution?.aton_sent"
                      class="btn btn--ghost btn--xs"
                      :title="editingAton ? 'Back to preview' : 'Edit draft'"
                      @click="editingAton = !editingAton"
                    >
                      {{ editingAton ? 'Preview' : '✎ Edit' }}
                    </button>
                    <button
                      class="btn btn--primary btn--sm"
                      :disabled="submittingAton || card.resolution?.aton_sent"
                      @click="submitAton"
                    >
                      <span v-if="submittingAton" class="spinner spinner--sm" />
                      {{ card.resolution?.aton_sent ? 'Sent ✓' : `➤ ${shortContact(atonContact)}` }}
                    </button>
                  </div>
                </div>
                <!-- Formatted preview -->
                <div
                  v-if="!editingAton"
                  class="modal__draft-preview"
                  v-html="renderDraft(atonDraft)"
                />
                <!-- Edit mode -->
                <textarea
                  v-else
                  v-model="atonDraft"
                  class="modal__textarea"
                  :disabled="card.resolution?.aton_sent"
                  placeholder="AI-generated draft will appear here…"
                />
              </div>

              <!-- Bottom-right: Customer response -->
              <div class="modal__response">
                <div class="modal__response-header">
                  <h3 class="modal__panel-title">Response to Customer</h3>
                  <div class="modal__response-actions">
                    <button
                      v-if="!card.resolution?.customer_sent"
                      class="btn btn--ghost btn--xs"
                      :title="editingCustomer ? 'Back to preview' : 'Edit draft'"
                      @click="editingCustomer = !editingCustomer"
                    >
                      {{ editingCustomer ? 'Preview' : '✎ Edit' }}
                    </button>
                    <button
                      class="btn btn--primary btn--sm"
                      :disabled="submittingCustomer || card.resolution?.customer_sent"
                      @click="submitCustomer"
                    >
                      <span v-if="submittingCustomer" class="spinner spinner--sm" />
                      {{ card.resolution?.customer_sent ? 'Sent ✓' : `➤ ${shortContact(customerContact)}` }}
                    </button>
                  </div>
                </div>
                <!-- Formatted preview -->
                <div
                  v-if="!editingCustomer"
                  class="modal__draft-preview"
                  v-html="renderDraft(customerDraft)"
                />
                <!-- Edit mode -->
                <textarea
                  v-else
                  v-model="customerDraft"
                  class="modal__textarea"
                  :disabled="card.resolution?.customer_sent"
                  placeholder="AI-generated draft will appear here…"
                />
              </div>
            </div>
            </div><!-- /.modal__reviews -->
          </template>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { api } from '../services/api'
import { useTransferStore } from '../stores/transfers'
import { REJECTION_CODE_DESCRIPTIONS } from '../services/rejectionCodes'

const props = defineProps({
  card: { type: Object, default: null },
})
const emit = defineEmits(['close'])

const store          = useTransferStore()
const submittingAton     = ref(false)
const submittingCustomer = ref(false)
const atonDraft          = ref('')
const customerDraft      = ref('')
const editingAton        = ref(false)
const editingCustomer    = ref(false)

// Renders a draft string: escapes HTML, converts **bold** and \n
function renderDraft(text) {
  if (!text) return '<span style="opacity:0.4">AI-generated draft will appear here…</span>'
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  const bolded = escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  return bolded.replace(/\n/g, '<br>')
}

// Pre-fill drafts when card changes (no longer auto-moves to in_review on open)
watch(
  () => props.card,
  (newCard) => {
    if (!newCard) return
    atonDraft.value     = newCard.resolution?.aton_response_draft     ?? ''
    customerDraft.value = newCard.resolution?.customer_response_draft ?? ''
  },
  { immediate: true }
)

// Refill drafts reactively as resolution arrives via WebSocket
watch(
  () => props.card?.resolution,
  (res) => {
    if (!res) return
    if (!atonDraft.value)     atonDraft.value     = res.aton_response_draft     ?? ''
    if (!customerDraft.value) customerDraft.value = res.customer_response_draft ?? ''
  }
)

function handleBackdropClick() {
  emit('close')
}

async function moveToReview() {
  if (!props.card) return
  await api.moveToReview(props.card.card_id)
  emit('close')
}

async function submitAton() {
  if (!props.card || submittingAton.value) return
  submittingAton.value = true
  try {
    await api.sendAton(props.card.card_id, atonDraft.value)
    // WebSocket will push updated card; check if both are now sent
  } catch (err) {
    console.error('Send ATON failed:', err)
  } finally {
    submittingAton.value = false
  }
}

async function submitCustomer() {
  if (!props.card || submittingCustomer.value) return
  submittingCustomer.value = true
  try {
    await api.sendCustomer(props.card.card_id, customerDraft.value)
  } catch (err) {
    console.error('Send customer failed:', err)
  } finally {
    submittingCustomer.value = false
  }
}

// ── Computed ─────────────────────────────────────────────────────────
const isExtracting = computed(
  () => !props.card?.pipeline_status || props.card?.pipeline_status === 'incoming'
)

const previewImageUrl = computed(
  () => props.card ? `/api/transfer/${props.card.card_id}/preview-image` : ''
)

const pipelineLabel = computed(() => {
  const s = props.card?.pipeline_status
  if (s === 'incoming')   return 'Extracting ATON fields…'
  if (s === 'aton_ready') return 'AI resolution in progress…'
  if (s === 'all_ready')  return 'Ready for review'
  return ''
})

// FAX image load state — reset each time the card changes or pipeline advances
const faxImageLoaded = ref(false)
const faxImageError  = ref(false)
const faxImageKey    = ref(0)    // incrementing forces <img> remount (retry on error)
const faxRetryCount  = ref(0)

function onFaxError() {
  // Retry up to 4 times with a 1.5 s delay before showing the error state
  if (faxRetryCount.value < 4) {
    faxRetryCount.value++
    setTimeout(() => {
      faxImageLoaded.value = false
      faxImageError.value  = false
      faxImageKey.value++          // forces Vue to remount the img → retries fetch
    }, 1500)
  } else {
    faxImageError.value = true
  }
}

watch(
  () => props.card?.card_id,
  () => {
    faxImageLoaded.value = false
    faxImageError.value  = false
    faxImageKey.value    = 0
    faxRetryCount.value  = 0
  }
)
// Reset FAX state when pipeline_status transitions out of incoming
watch(
  () => props.card?.pipeline_status,
  (newStatus, oldStatus) => {
    if (oldStatus === 'incoming' && newStatus && newStatus !== 'incoming') {
      faxImageLoaded.value = false
      faxImageError.value  = false
      faxImageKey.value++
      faxRetryCount.value  = 0
    }
  }
)

// Email formatted lines: bold the "Label" part before the first colon
const emailLines = computed(() => {
  const text = props.card?.file_preview_text ?? ''
  if (!text) return []
  return text.split('\n').map(line => {
    const colonIdx = line.indexOf(':')
    // Only treat as labeled if colon is within first 40 chars and not at position 0
    if (colonIdx > 0 && colonIdx <= 40) {
      return { label: line.slice(0, colonIdx), rest: line.slice(colonIdx) }
    }
    return { label: null, rest: line }
  })
})

// ── Helpers ──────────────────────────────────────────────────────────
// Which contact address to use for the ATON response (fax number for FAX type)
const atonContact = computed(() => {
  if (props.card?.input_type === 'FAX') {
    return props.card?.aton_message?.source_fax || props.card?.aton_message?.source_email || 'institution@fax'
  }
  return props.card?.aton_message?.source_email || 'institution@clearinghouse.ca'
})

const customerContact = computed(() => props.card?.customer?.email || 'client@email.com')

function formatSin(sin) {
  if (!sin) return '—'
  const s = sin.replace(/\D/g, '')
  return s.length === 9 ? `${s.slice(0, 3)} ${s.slice(3, 6)} ${s.slice(6)}` : sin
}

function shortContact(contact) {
  if (!contact) return '—'
  return contact.length > 28 ? contact.slice(0, 28) + '…' : contact
}

function codeDesc(code) {
  return REJECTION_CODE_DESCRIPTIONS[code] ?? 'Unknown rejection code'
}

const typeChipClass = computed(() => {
  const map = { Email: 'chip--email', FAX: 'chip--fax', PDF: 'chip--pdf' }
  return map[props.card?.input_type] ?? 'chip--email'
})
const dirChipClass = computed(() =>
  props.card?.aton_message?.transfer_type === 'Transfer In' ? 'chip--in' : 'chip--out'
)
const dirArrow = computed(() =>
  props.card?.aton_message?.transfer_type === 'Transfer In' ? '↓' : '↑'
)

const confidenceLabelColor = computed(() => {
  const s = props.card?.resolution?.confidence_score ?? 0
  if (s >= 0.70) return '#009e6c'
  if (s >= 0.50) return '#d4870e'
  return '#c0392b'
})

const confidenceBg = computed(() => {
  const s = props.card?.resolution?.confidence_score ?? 0
  if (s >= 0.70) return 'rgba(0, 158, 108, 0.14)'
  if (s >= 0.50) return 'rgba(212, 135, 14, 0.14)'
  return 'rgba(192, 57, 43, 0.14)'
})
</script>

<style scoped>
/* ── Backdrop ─────────────────────────────────────────────────────── */
.modal-backdrop {
  position:        fixed;
  inset:           0;
  z-index:         200;
  background:      rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(4px);
  display:         flex;
  align-items:     center;
  justify-content: center;
  padding:         16px;
}

/* ── Modal shell ──────────────────────────────────────────────────── */
.modal {
  background:     var(--bg-modal);
  border:         1px solid var(--border);
  border-radius:  var(--radius-xl);
  width:          90vw;
  max-width:      1600px;
  height:         90vh;
  max-height:     90vh;
  overflow:       hidden;
  display:        flex;
  flex-direction: column;
  gap:            0;
}

/* ── Header ───────────────────────────────────────────────────────── */
.modal__header {
  display:         flex;
  justify-content: space-between;
  align-items:     center;
  padding:         11px 28px;
  border-bottom:   1px solid var(--border-subtle);
  gap:             12px;
  position:        sticky;
  top:             0;
  background:      var(--bg-modal);
  z-index:         1;
  font-size:       1rem;
}

.modal__header-confidence {
  position:       absolute;
  left:           50%;
  transform:      translateX(-50%);
  font-size:      1.05rem;
  font-weight:    900;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  pointer-events: none;
  white-space:    nowrap;
  padding:        5px 18px;
  border-radius:  999px;
  border:         2px solid;
  box-shadow:     0 0 10px 2px var(--confidence-glow, rgba(0,158,108,0.35));
  /* background + borderColor come from inline :style */
}

.modal__header-left {
  display:     flex;
  align-items: center;
  gap:         10px;
  flex-wrap:   wrap;
}

.modal__close {
  flex-shrink: 0;
}

/* ── Reviews wrapper (in-review / responded) ──────────────────────── */
.modal__reviews {
  flex:           1;
  display:        flex;
  flex-direction: column;
  min-height:     0;
}

/* accounts two-column layout */
.accounts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 16px;
}

.chip--missing {
  background:      transparent;
  border:          1px dashed var(--border);
  color:           var(--text-muted);
  text-decoration: line-through;
  opacity:         0.7;
}

/* ── Top row ──────────────────────────────────────────────────────── */
.modal__top {
  display:   grid;
  grid-template-columns: 1fr 1fr;
  gap:       1px;
  background: var(--border-subtle);
}

.modal__panel {
  background: var(--bg-modal);
  padding:    22px 28px;
  overflow-y: auto;
  max-height: 48vh;
  font-size:  0.9375rem;
}

.modal__panel-title {
  font-size:      0.875rem;
  font-weight:    600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color:          var(--text-muted);
  margin-bottom:  14px;
}

/* ── Info grid ────────────────────────────────────────────────────── */
.info-grid {
  display:               grid;
  grid-template-columns: max-content 1fr;
  gap:                   7px 16px;
  font-size:             0.9375rem;
}

.info-grid--wide {
  grid-template-columns: max-content 1fr max-content 1fr;
  column-gap:            20px;
}

.info-grid dt {
  color:       var(--text-muted);
  font-weight: 500;
  white-space: nowrap;
}

.info-grid dd {
  color:     var(--text-primary);
  word-break: break-word;
}

/* ── Rejection codes ──────────────────────────────────────────────── */
.modal__codes {
  margin-top: 14px;
}

.rejection-code {
  display:     flex;
  align-items: flex-start;
  gap:         8px;
  padding:     5px 0;
  border-bottom: 1px solid var(--border-subtle);
}
.rejection-code:last-child { border-bottom: none; }

.rejection-code__badge { flex-shrink: 0; }
.rejection-code__desc  { flex: 1; padding-top: 2px; }
.rejection-code__match {
  flex-shrink:     0;
  font-size:       0.7rem;
  font-weight:     700;
  color:           #009e6c;
  background:      rgba(0,158,108,0.12);
  border:          1px solid rgba(0,158,108,0.4);
  border-radius:   999px;
  padding:         1px 8px;
  white-space:     nowrap;
  align-self:      center;
}

.chip--code {
  background: rgba(0, 0, 0, 0.06);
  color:      var(--text-muted);
  border:     1px solid var(--border);
  font-size:  0.7rem;
}

/* ── Account chips ────────────────────────────────────────────────── */
.account-chips {
  display:   flex;
  flex-wrap: wrap;
  gap:       6px;
}

/* ── TFSA Holdings ────────────────────────────────────────────────── */
.holdings {
  display:   flex;
  flex-wrap: wrap;
  gap:       6px;
}

.holding {
  display:       flex;
  flex-direction: column;
  align-items:   center;
  background:    var(--bg-elevated);
  border:        1px solid var(--border);
  border-radius: var(--radius-sm);
  padding:       4px 8px;
  min-width:     72px;
  text-align:    center;
}

/* ── Bottom row ───────────────────────────────────────────────────── */
.modal__bottom {
  display:    grid;
  grid-template-columns: 1fr 1fr;
  gap:        1px;
  background: var(--border-subtle);
  border-top: 1px solid var(--border-subtle);
  flex:       1;
  min-height: 0;
}

.modal__response {
  background:     var(--bg-modal);
  padding:        16px 28px 20px;
  display:        flex;
  flex-direction: column;
  gap:            10px;
  font-size:      0.9375rem;
  flex:           1;
  min-height:     0;
}

.modal__response-header {
  display:         flex;
  align-items:     center;
  justify-content: space-between;
  gap:             12px;
  flex-shrink:     0;
}

.modal__response-actions {
  display:     flex;
  align-items: center;
  gap:         8px;
  flex-shrink: 0;
}

/* Formatted draft preview */
.modal__draft-preview {
  flex:          1;
  min-height:    140px;
  background:    var(--bg-elevated);
  border:        1px solid var(--border);
  border-radius: var(--radius);
  color:         var(--text-primary);
  font-family:   var(--font);
  font-size:     0.9375rem;
  line-height:   1.8;
  padding:       14px 16px;
  overflow-y:    auto;
  white-space:   pre-wrap;
  word-break:    break-word;
}

.modal__textarea {
  width:        100%;
  flex:         1;
  min-height:   140px;
  background:   var(--bg-elevated);
  border:       1px solid var(--border);
  border-radius: var(--radius);
  color:        var(--text-primary);
  font-family:  var(--font);
  font-size:    0.9375rem;
  line-height:  1.6;
  padding:      14px 16px;
  resize:       vertical;
  transition:   border-color var(--transition);
  outline:      none;
}

.modal__textarea:focus {
  border-color: var(--accent);
}

/* ── Spinner ──────────────────────────────────────────────────────── */
.spinner {
  display:       inline-block;
  width:         12px;
  height:        12px;
  border:        2px solid var(--border);
  border-top:    2px solid var(--accent);
  border-radius: 50%;
  animation:     spin 0.8s linear infinite;
  vertical-align: middle;
}

.spinner--sm {
  display:       inline-block;
  width:         12px;
  height:        12px;
  border:        2px solid rgba(0,0,0,0.2);
  border-top:    2px solid #000;
  border-radius: 50%;
  animation:     spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Incoming dual-column layout ─────────────────────────────────── */
.modal__incoming {
  display:  grid;
  grid-template-columns: 1fr 1fr;
  gap:      1px;
  background: var(--border-subtle);
  flex:     1;
  overflow: hidden;
  min-height: 0;
}

/* Panels inside incoming: fill the full available height */
.modal__incoming .modal__panel {
  max-height: none;
  height:     100%;
  overflow-y: auto;
}

.modal__incoming .modal__panel--preview {
  max-height: none;
  height:     100%;
  display:    flex;
  flex-direction: column;
}

.modal__panel--preview {
  overflow:       hidden;
  max-height:     70vh;
  display:        flex;
  flex-direction: column;
  gap:            12px;
}

/* FAX loading placeholder */
.preview-loading {
  display:         flex;
  flex-direction:  column;
  align-items:     center;
  justify-content: center;
  gap:             12px;
  min-height:      220px;
  color:           var(--text-muted);
  font-size:       0.875rem;
}

.preview-loading .spinner {
  width:        32px;
  height:       32px;
  border-width: 3px;
}

.preview-img {
  width:         100%;
  flex:          1;
  min-height:    0;
  object-fit:    contain;
  border-radius: var(--radius);
  border:        1px solid var(--border);
  display:       block;
  transition:    opacity 0.3s ease;
}

.preview-img--hidden {
  display: none;
}

/* PDF native browser embed */
.preview-pdf {
  width:         100%;
  flex:          1;
  min-height:    0;
  border:        1px solid var(--border);
  border-radius: var(--radius);
  display:       block;
}

/* Email formatted preview */
.preview-email {
  font-family:  var(--font);
  font-size:    0.875rem;
  line-height:  1.7;
  color:        var(--text-secondary);
  background:   var(--bg-elevated);
  border:       1px solid var(--border);
  border-radius: var(--radius);
  padding:      14px 18px;
  overflow-y:   auto;
  flex:         1;
  min-height:   0;
}

.preview-email__line {
  margin:     0;
  word-break: break-word;
}

.preview-email__label {
  font-weight: 700;
  color:       var(--text-primary);
}

.preview-email__rest {
  color: var(--text-secondary);
}

/* Legacy plain-text preview still referenced elsewhere */
.preview-text {
  font-family:  var(--font-mono);
  font-size:    0.8125rem;
  line-height:  1.6;
  color:        var(--text-secondary);
  white-space:  pre-wrap;
  word-break:   break-word;
  background:   var(--bg-elevated);
  border:       1px solid var(--border);
  border-radius: var(--radius);
  padding:      12px 14px;
  overflow-y:   auto;
  max-height:   55vh;
}

.modal__incoming-footer {
  display:         flex;
  align-items:     center;
  justify-content: space-between;
  padding:         14px 24px;
  border-top:      1px solid var(--border-subtle);
  gap:             12px;
  background:      var(--bg-modal);
  flex-shrink:     0;
}

/* ── Skeleton loading ─────────────────────────────────────────────── */
.skeleton-grid {
  display:        flex;
  flex-direction: column;
  gap:            10px;
}

.skeleton-row {
  display:     flex;
  align-items: center;
  gap:         12px;
}

.skeleton {
  height:        12px;
  border-radius: 6px;
  background:    linear-gradient(
    90deg,
    var(--bg-elevated) 25%,
    var(--bg-hover)    50%,
    var(--bg-elevated) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite linear;
}

.skeleton--label {
  width:      80px;
  flex-shrink: 0;
}

.skeleton--value {
  flex: 1;
}

@keyframes shimmer {
  from { background-position: 200% 0; }
  to   { background-position: -200% 0; }
}

/* ── Pipeline status badge in header ──────────────────────────────── */
.pipeline-badge {
  font-size:     0.7rem;
  font-weight:   500;
  color:         var(--text-muted);
  background:    var(--bg-elevated);
  border:        1px solid var(--border);
  border-radius: 100px;
  padding:       2px 8px;
  letter-spacing: 0.01em;
}

/* Review button — grey when waiting, green when all_ready */
.btn--review:disabled {
  opacity: 0.45;
  cursor:  not-allowed;
}

/* ── Modal transition ─────────────────────────────────────────────── */
.modal-enter-active, .modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-active .modal, .modal-leave-active .modal {
  transition: transform 0.2s ease, opacity 0.2s ease;
}
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from .modal, .modal-leave-to .modal {
  transform: scale(0.97) translateY(12px);
}
</style>
