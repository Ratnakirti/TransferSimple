<template>
  <div class="kanban">
    <KanbanColumn
      title="Incoming"
      :cards="store.incoming"
      column-key="incoming"
      @open-card="$emit('open-card', $event)"
      @clear-all="handleClearAll"
    />
    <KanbanColumn
      title="In Review"
      :cards="store.inReview"
      column-key="in_review"
      @open-card="$emit('open-card', $event)"
      @clear-all="handleClearAll"
    />
    <KanbanColumn
      title="Responded"
      :cards="store.responded"
      column-key="responded"
      @open-card="$emit('open-card', $event)"
      @clear-all="handleClearAll"
    />
  </div>
</template>

<script setup>
import { useTransferStore } from '../stores/transfers'
import KanbanColumn from './KanbanColumn.vue'
import { api } from '../services/api'

const store = useTransferStore()
defineEmits(['open-card'])

async function handleClearAll(columnKey) {
  if (columnKey === 'in_review') {
    // Move all cards in review back to incoming
    await api.requeueReview()
    // WebSocket will broadcast card_updated with state=incoming for each
  } else {
    // Delete all cards in this column
    await api.clearColumn(columnKey)
    // WebSocket will broadcast card_removed for each; also clear locally for instant feedback
    store.clearColumnLocally(columnKey)
  }
}
</script>

<style scoped>
.kanban {
  display:    flex;
  gap:        16px;
  height:     100%;
  padding:    20px;
  overflow-x: auto;
  align-items: stretch;
}
</style>
