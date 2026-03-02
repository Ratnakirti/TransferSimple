<template>
  <div class="column">
    <div class="column__header">
      <span class="column__title">{{ title }}</span>
      <span class="column__count">{{ cards.length }}</span>
    </div>

    <div class="column__body">
      <TransitionGroup name="card-list" tag="div" class="column__cards">
        <TransferCard
          v-for="card in cards"
          :key="card.card_id"
          :card="card"
          @open="$emit('open-card', card)"
        />
      </TransitionGroup>

      <div v-if="cards.length === 0" class="column__empty text-muted text-sm">
        No transfers
      </div>
    </div>

    <!-- Footer with Clear All button -->
    <div class="column__footer">
      <button
        class="btn btn--ghost btn--xs column__clear-btn"
        :disabled="cards.length === 0"
        @click="$emit('clear-all', columnKey)"
      >
        {{ columnKey === 'in_review' ? 'Return All to Incoming' : 'Clear All' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import TransferCard from './TransferCard.vue'

defineProps({
  title:     { type: String,  required: true },
  cards:     { type: Array,   default: () => [] },
  columnKey: { type: String,  required: true },
})
defineEmits(['open-card', 'clear-all'])
</script>

<style scoped>
.column {
  display:        flex;
  flex-direction: column;
  flex:           1 1 0;
  min-width:      280px;
  background:     var(--bg-surface);
  border:         1px solid var(--border-subtle);
  border-radius:  var(--radius-xl);
  overflow:       hidden;
}

.column__header {
  display:         flex;
  justify-content: space-between;
  align-items:     center;
  padding:         16px 18px 14px;
  border-bottom:   1px solid var(--border-subtle);
}

.column__title {
  font-size:   0.9375rem;
  font-weight: 600;
  color:       var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.column__count {
  display:         inline-flex;
  align-items:     center;
  justify-content: center;
  min-width:       22px;
  height:          22px;
  padding:         0 6px;
  background:      var(--bg-elevated);
  border:          1px solid var(--border);
  border-radius:   100px;
  font-size:       0.75rem;
  font-weight:     600;
  color:           var(--text-secondary);
}

.column__body {
  flex:       1;
  overflow-y: auto;
  padding:    12px;
}

.column__cards {
  display:        flex;
  flex-direction: column;
  gap:            10px;
}

.column__empty {
  text-align: center;
  padding:    32px 0;
}

/* Column footer with Clear All */
.column__footer {
  padding:         8px 12px;
  border-top:      1px solid var(--border-subtle);
  display:         flex;
  justify-content: flex-end;
  flex-shrink:     0;
}

.column__clear-btn {
  font-size:   0.72rem;
  color:       var(--text-muted);
  opacity:     0.7;
}
.column__clear-btn:hover:not(:disabled) {
  color:   var(--text-primary);
  opacity: 1;
}

/* Card list transition */
.card-list-enter-active,
.card-list-leave-active { transition: all 0.3s ease; }
.card-list-enter-from   { opacity: 0; transform: translateY(-12px); }
.card-list-leave-to     { opacity: 0; transform: translateX(12px); }
.card-list-move         { transition: transform 0.3s ease; }
</style>
