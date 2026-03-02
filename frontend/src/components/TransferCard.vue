<template>
  <div class="card card--clickable transfer-card" @click="$emit('open', card)">
    <!-- Row 1: type chip + ticket id + confidence chip (inline for in-review) -->
    <div class="transfer-card__header">
      <span class="text-mono transfer-card__ticket">{{ card.aton_message?.ticket_id ?? '—' }}</span>
      <div class="transfer-card__header-right">
        <span :class="['chip', typeChipClass]">{{ card.input_type }}</span>
        <span
          v-if="card.state === 'in_review' && card.resolution?.confidence_score != null"
          class="confidence-chip"
          :style="{ color: confidenceColor, borderColor: confidenceColor }"
        >
          {{ Math.round(card.resolution.confidence_score * 100) }}%
        </span>
      </div>
    </div>

    <!-- Row 2: transfer direction -->
    <div class="transfer-card__direction">
      <span :class="['chip', dirChipClass]">
        {{ dirArrow }} {{ card.aton_message?.transfer_type ?? 'Processing…' }}
      </span>
    </div>

    <!-- Row 3: institution names (if available) -->
    <div v-if="card.aton_message" class="transfer-card__meta text-xs text-secondary">
      <span>{{ card.aton_message.delivering_institution }}</span>
      <span class="transfer-card__arrow">→</span>
      <span>{{ card.aton_message.receiving_institution }}</span>
    </div>

    <!-- Loading state -->
    <div v-if="isProcessing" class="transfer-card__loading text-xs text-muted">
      <span class="spinner" /> Processing…
    </div>

    <!-- Rejection codes -->
    <div
      v-if="card.aton_message?.rejection_codes?.length"
      class="transfer-card__codes"
    >
      <span
        v-for="code in card.aton_message.rejection_codes"
        :key="code"
        class="chip chip--code"
        :title="code"
      >
        {{ code }}
      </span>
    </div>

    <!-- Sent indicators (responded cards) -->
    <div v-if="card.state === 'responded'" class="transfer-card__sent">
      <span :class="['sent-indicator', card.resolution?.aton_sent ? 'sent-indicator--done' : 'sent-indicator--pending']">
        ATON {{ card.resolution?.aton_sent ? '✓' : '○' }}
      </span>
      <span :class="['sent-indicator', card.resolution?.customer_sent ? 'sent-indicator--done' : 'sent-indicator--pending']">
        Client {{ card.resolution?.customer_sent ? '✓' : '○' }}
      </span>
    </div>

  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  card: { type: Object, required: true },
})
defineEmits(['open'])

const isProcessing = computed(
  () =>
    props.card.state === 'incoming' &&
    (!props.card.pipeline_status || props.card.pipeline_status === 'incoming')
)

const typeChipClass = computed(() => {
  const map = { Email: 'chip--email', FAX: 'chip--fax', PDF: 'chip--pdf' }
  return map[props.card.input_type] ?? 'chip--email'
})

const dirChipClass = computed(() =>
  props.card.aton_message?.transfer_type === 'Transfer In'
    ? 'chip--in'
    : 'chip--out'
)

const dirArrow = computed(() =>
  props.card.aton_message?.transfer_type === 'Transfer In' ? '↓' : '↑'
)

const confidenceColor = computed(() => {
  const s = props.card.resolution?.confidence_score ?? 0
  if (s >= 0.70) return '#009e6c'
  if (s >= 0.50) return '#d4870e'
  return '#c0392b'
})
</script>

<style scoped>
.transfer-card {
  display:        flex;
  flex-direction: column;
  gap:            10px;
}

.transfer-card__header {
  display:         flex;
  justify-content: space-between;
  align-items:     center;
  gap:             8px;
}

.transfer-card__header-right {
  display:     flex;
  align-items: center;
  gap:         6px;
  flex-shrink: 0;
}

.transfer-card__ticket {
  font-size:   1.0625rem;
  font-weight: 600;
  color:       var(--text-primary);
  word-break: break-all;
}

.transfer-card__direction {
  display: flex;
}

.transfer-card__meta {
  display:     flex;
  align-items: center;
  gap:         6px;
  flex-wrap:   wrap;
  color:       var(--text-secondary);
  font-size:   0.875rem;
}

.transfer-card__arrow {
  color: var(--text-muted);
}

.transfer-card__codes {
  display:   flex;
  flex-wrap: wrap;
  gap:       4px;
}

.chip--code {
  background: rgba(255, 255, 255, 0.05);
  color:      var(--text-muted);
  border:     1px solid var(--border);
  font-size:  0.7rem;
}

.transfer-card__loading {
  display:     flex;
  align-items: center;
  gap:         6px;
}

.transfer-card__sent {
  display:   flex;
  gap:       6px;
  flex-wrap: wrap;
  margin-top: 2px;
}

.sent-indicator {
  font-size:     0.7rem;
  font-weight:   600;
  padding:       2px 7px;
  border-radius: var(--radius-sm);
  border:        1px solid;
  white-space:   nowrap;
}

.sent-indicator--done {
  color:            var(--accent);
  border-color:     var(--accent);
  background:       var(--accent-dim);
}

.sent-indicator--pending {
  color:        var(--text-muted);
  border-color: var(--border);
  background:   transparent;
}

.confidence-chip {
  font-size:     0.8125rem;
  font-weight:   700;
  border:        1.5px solid;
  border-radius: 50%;
  width:         36px;
  height:        36px;
  display:       inline-flex;
  align-items:   center;
  justify-content: center;
  line-height:   1;
}

/* Loading spinner */
.spinner {
  display:       inline-block;
  width:         12px;
  height:        12px;
  border:        2px solid var(--border);
  border-top:    2px solid var(--accent);
  border-radius: 50%;
  animation:     spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
