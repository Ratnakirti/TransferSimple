<template>
  <div class="confidence">
    <!-- SVG arc gauge — 96 px, 5/6 circle, just the % number inside -->
    <svg class="confidence__gauge" viewBox="0 0 60 60">
      <!-- Background track -->
      <circle
        cx="30" cy="30" r="24"
        fill="none"
        stroke="var(--bg-elevated)"
        stroke-width="5"
        stroke-dasharray="125.66 150.80"
        stroke-dashoffset="-12.57"
        stroke-linecap="round"
        transform="rotate(-210 30 30)"
      />
      <!-- Foreground arc -->
      <circle
        cx="30" cy="30" r="24"
        fill="none"
        :stroke="arcColour"
        stroke-width="5"
        :stroke-dasharray="`${arcLength} 150.80`"
        stroke-dashoffset="-12.57"
        stroke-linecap="round"
        transform="rotate(-210 30 30)"
        class="confidence__arc"
      />
      <!-- Centered % label inside the SVG -->
      <text
        x="30" y="35"
        text-anchor="middle"
        dominant-baseline="middle"
        :fill="arcColour"
        font-size="13"
        font-weight="700"
        font-family="'DM Sans', sans-serif"
      >{{ pct }}%</text>
    </svg>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  score:     { type: Number, default: 0 },   // 0.0 – 1.0
  reasoning: { type: String, default: '' },  // kept for compat, no longer displayed
})

const pct = computed(() => Math.round(props.score * 100))

// Arc circumference for r=24 full circle ≈ 150.80; show 5/6 = 125.66
const arcLength = computed(() => (pct.value / 100) * 125.66)

const arcColour = computed(() => {
  if (props.score >= 0.70) return '#009e6c'
  if (props.score >= 0.50) return '#d4870e'
  return '#c0392b'
})
</script>

<style scoped>
.confidence {
  display:         flex;
  align-items:     center;
  justify-content: center;
}

.confidence__gauge {
  width:  96px;
  height: 96px;
}

.confidence__arc {
  transition: stroke-dasharray 0.4s ease;
}
</style>
