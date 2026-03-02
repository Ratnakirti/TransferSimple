<template>
  <div class="app">

    <!-- ── Welcome page ──────────────────────── -->
    <WelcomePage v-if="showWelcome" @enter="showWelcome = false" />

    <template v-else>
      <!-- ── Top nav ──────────────────────────────────────── -->
      <header class="nav">
        <div class="nav__brand">
          <span class="nav__logo">TransferSimple</span>
          <span class="nav__tag text-xs text-muted">ATON Transfer Resolution Platform</span>
        </div>

        <div class="nav__status">
          <span :class="['status-dot', health === 'ok' ? 'status-dot--green' : 'status-dot--red']" />
          <span class="text-xs text-muted">
            {{ health === 'ok' ? 'All systems operational' : health === 'loading' ? 'Connecting…' : 'Backend unreachable' }}
          </span>
        </div>
      </header>

      <!-- ── Board ───────────────────────────────────────── -->
      <main class="app__main">
        <KanbanBoard @open-card="openCard" />
      </main>

      <!-- ── Card modal ──────────────────────────────────── -->
      <CardModal :card="activeCard" @close="closeCard" />

      <!-- ── Sim panel (hidden trigger) ──────────────────── -->
      <SimPanel />

      <!-- ── Toast (warn / error) ──────────────────────── -->
      <Transition name="toast">
        <div v-if="toastVisible" :class="['toast', `toast--${toastType}`]">
          {{ toastMessage }}
        </div>
      </Transition>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import WelcomePage    from './components/WelcomePage.vue'
import KanbanBoard    from './components/KanbanBoard.vue'
import CardModal      from './components/CardModal.vue'
import SimPanel       from './components/SimPanel.vue'
import { useTransferStore } from './stores/transfers'
import { api } from './services/api'

const store        = useTransferStore()
const activeCardId = ref(null)
// Computed so the modal always shows the latest store value (tracks WebSocket updates)
const activeCard   = computed(() => activeCardId.value ? store.cards[activeCardId.value] ?? null : null)
const health       = ref('loading')
const showWelcome  = ref(true)
const toastVisible = ref(false)
const toastMessage = ref('')
const toastType    = ref('warn')   // 'warn' | 'error'
let   _toastTimer  = null
let   _toastDelay  = null

function openCard(card) {
  activeCardId.value = card.card_id
  const score = card.resolution?.confidence_score ?? null
  if (card.state === 'in_review' && score !== null && score < 0.75) {
    if (_toastDelay) clearTimeout(_toastDelay)
    _toastDelay = setTimeout(() => showToast('⚠ Low confidence — review rejection codes carefully', 'warn'), 1000)
  }
}

function showToast(message, type = 'warn', duration = 4000) {
  if (_toastTimer) clearTimeout(_toastTimer)
  toastMessage.value = message
  toastType.value    = type
  toastVisible.value = true
  _toastTimer = setTimeout(() => { toastVisible.value = false }, duration)
}

function closeCard() {
  activeCardId.value = null
}

onMounted(async () => {
  store.startListening()

  // Show pipeline errors as a red toast
  window.addEventListener('card-pipeline-error', (e) => {
    showToast(`❌ Pipeline error: ${e.detail.error}`, 'error', 7000)
  })

  try {
    const res = await api.health()
    health.value = res.data?.status === 'ok' ? 'ok' : 'degraded'
  } catch {
    health.value = 'error'
  }
  // Rehydrate board from backend in case of page refresh
  try {
    const res = await api.getTransfers()
    for (const card of (res.data ?? [])) {
      store.upsertCard(card)
    }
  } catch { /* non-critical */ }
})

onUnmounted(() => {
  store.stopListening()
})
</script>

<style scoped>
.app {
  display:        flex;
  flex-direction: column;
  height:         100vh;
  overflow:       hidden;
}

/* ── Nav ──────────────────────────────────────────────── */
.nav {
  display:         flex;
  justify-content: space-between;
  align-items:     center;
  padding:         0 24px;
  height:          56px;
  flex-shrink:     0;
  border-bottom:   1px solid var(--border-subtle);
  background:      var(--bg-surface);
}

.nav__brand {
  display:     flex;
  align-items: baseline;
  gap:         10px;
}

.nav__logo {
  font-size:   1.4rem;
  font-weight: 700;
  font-family: 'Times New Roman', Times, serif;
  color:       var(--accent);
  letter-spacing: -0.02em;
  line-height: 1;
}

.nav__tag {
  letter-spacing: 0.04em;
}

.nav__status {
  display:     flex;
  align-items: center;
  gap:         6px;
}

.status-dot {
  width:         8px;
  height:        8px;
  border-radius: 50%;
  flex-shrink:   0;
}
.status-dot--green { background: var(--accent);   box-shadow: 0 0 6px var(--accent); }
.status-dot--red   { background: var(--red);      box-shadow: 0 0 6px var(--red); }

/* ── Main ─────────────────────────────────────────────── */
.app__main {
  flex:             1;
  overflow:         hidden;
  background-color: var(--bg-base);
}

/* ── Toast ────────────────────────────────────────────── */
.toast {
  position:      fixed;
  top:           380px;
  left:          50%;
  transform:     translateX(-50%);
  z-index:       9999;
  padding:       10px 22px;
  border-radius: 8px;
  font-size:     0.85rem;
  font-weight:   600;
  white-space:   nowrap;
  pointer-events: none;
  box-shadow:    0 4px 18px rgba(0,0,0,0.4);
}
.toast--warn  {
  background: #3a2600;
  color:      #ffb547;
  border:     1px solid #ffb547;
}
.toast--error {
  background: #2a0000;
  color:      #ff6b6b;
  border:     1px solid #ff6b6b;
}

/* toast slide-down transition */
.toast-enter-active, .toast-leave-active { transition: opacity 0.25s ease, transform 0.25s ease; }
.toast-enter-from  { opacity: 0; transform: translateX(-50%) translateY(-10px); }
.toast-leave-to    { opacity: 0; transform: translateX(-50%) translateY(-10px); }
</style>
