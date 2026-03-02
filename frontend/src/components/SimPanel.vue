<template>
  <div class="sim-panel" :class="{ 'sim-panel--open': isOpen }">
    <!-- Toggle tab -->
    <button class="sim-panel__tab text-xs font-medium" @click="isOpen = !isOpen">
      {{ isOpen ? '✕ Close' : '⚡ SIM' }}
    </button>

    <!-- Sim buttons -->
    <Transition name="fade">
      <div v-show="isOpen" class="sim-panel__buttons">
        <p class="text-xs text-muted sim-panel__label">Trigger simulation</p>
        <button
          v-for="n in 4"
          :key="n"
          class="btn btn--ghost btn--sm sim-panel__btn"
          :disabled="loading[n]"
          @click="triggerSim(n)"
        >
          <span v-if="loading[n]" class="spinner spinner--sm" />
          SIM {{ n }}
          <span v-if="n === 4" class="chip chip--amber text-xs" style="margin-left:2px">×3</span>
        </button>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { api } from '../services/api'
import { useTransferStore } from '../stores/transfers'

const store   = useTransferStore()
const isOpen  = ref(false)
const loading = reactive({ 1: false, 2: false, 3: false, 4: false })

async function triggerSim(n) {
  loading[n] = true
  isOpen.value = false   // collapse immediately when a SIM is chosen
  try {
    const res = await api.triggerSim(n)
    // Pre-populate placeholder cards so they appear immediately
    const cardIds = res.data?.card_ids ?? []
    const typeMap = { 1: 'Email', 2: 'FAX', 3: 'PDF' }
    const simTypes = n === 4 ? ['Email', 'FAX', 'PDF'] : [typeMap[n]]

    cardIds.forEach((id, i) => {
      store.upsertCard({
        card_id:      id,
        input_type:   simTypes[i] ?? 'Email',
        state:        'incoming',
        aton_message: null,
        customer:     null,
        resolution:   null,
      })
    })
  } catch (err) {
    console.error('Sim trigger failed:', err)
  } finally {
    loading[n] = false
  }
}
</script>

<style scoped>
.sim-panel {
  position:       fixed;
  bottom:         24px;
  left:           24px;
  z-index:        100;
  display:        flex;
  flex-direction: column;
  align-items:    flex-start;
  gap:            8px;
}

.sim-panel__tab {
  background:    var(--bg-elevated);
  border:        1px solid var(--border);
  border-radius: var(--radius);
  color:         var(--text-secondary);
  padding:       6px 12px;
  cursor:        pointer;
  font-family:   var(--font);
  transition:    background var(--transition), color var(--transition);
}
.sim-panel__tab:hover {
  background: var(--bg-hover);
  color:      var(--text-primary);
}

.sim-panel__buttons {
  background:    var(--bg-elevated);
  border:        1px solid var(--border);
  border-radius: var(--radius-lg);
  padding:       12px;
  display:       flex;
  flex-direction: column;
  gap:           8px;
  min-width:     140px;
  order:         -1;
}

.sim-panel__label {
  padding-bottom: 4px;
  border-bottom:  1px solid var(--border-subtle);
}

.sim-panel__btn {
  justify-content: flex-start;
  width: 100%;
}

.chip--amber {
  background:   var(--amber-dim);
  color:        var(--amber);
  padding:      1px 5px;
  border-radius: 4px;
}

.spinner--sm {
  display:       inline-block;
  width:         10px;
  height:        10px;
  border:        2px solid var(--border);
  border-top:    2px solid var(--accent);
  border-radius: 50%;
  animation:     spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* Fade transition for the buttons panel */
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.fade-enter-from, .fade-leave-to       { opacity: 0; transform: translateY(6px); }
</style>
