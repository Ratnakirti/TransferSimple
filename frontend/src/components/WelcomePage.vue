<template>
  <div class="welcome">
    <!-- Full-page background image -->
    <div class="welcome__bg" />

    <!-- Overlay content — left-aligned, indented from left edge -->
    <div class="welcome__content">
      <h1 class="welcome__title">TransferSimple</h1>
      <p class="welcome__subtitle">ATON Transfer Resolution Platform</p>
      <button class="welcome__cta" @click="$emit('enter')">
        Launch App
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import bgImage from '../assets/Welcome_BG.png'
defineEmits(['enter'])

const bgUrl = computed(() => `url(${bgImage})`)
</script>

<style scoped>
.welcome {
  position:   relative;
  height:     100vh;
  width:      100%;
  overflow:   hidden;
  font-family: 'Times New Roman', Times, serif;
}

.welcome__bg {
  position:            absolute;
  inset:               0;
  background-image:    v-bind(bgUrl);
  background-size:     cover;
  background-position: center center;
  background-repeat:   no-repeat;
  z-index:             0;
}

.welcome__content {
  position:       relative;
  z-index:        1;
  height:         100%;
  display:        flex;
  flex-direction: column;
  justify-content: center;
  padding-left:   8vw;
  padding-bottom: 4vh;
  gap:            20px;
}

.welcome__title {
  font-family:    'Times New Roman', Times, serif;
  font-size:      clamp(3.5rem, 8vw, 7rem);
  font-weight:    700;
  color:          #1a1a1a;
  line-height:    1.05;
  letter-spacing: -0.01em;
  margin:         0;
  text-shadow:    0 2px 20px rgba(255, 255, 255, 0.25);
}

.welcome__subtitle {
  font-family:    'DM Sans', sans-serif;
  font-size:      clamp(1.1rem, 2.4vw, 1.75rem);
  font-weight:    400;
  color:          rgba(0, 0, 0, 0.75);
  letter-spacing: 0.04em;
  margin:         0;
  text-shadow:    none;
}

.welcome__cta {
  margin-top:      12px;
  display:         inline-flex;
  align-items:     center;
  justify-content: center;
  padding:         14px 44px;
  background:      #b8ddc8;
  color:           #1a1a1a;
  border:          none;
  border-radius:   6px;
  font-family:     'DM Sans', sans-serif;
  font-size:       1.1rem;
  font-weight:     500;
  letter-spacing:  0.04em;
  cursor:          pointer;
  transition:      background 180ms ease, transform 120ms ease;
  width:           fit-content;
}
.welcome__cta:hover {
  background:  #a2d4b7;
  transform:   translateY(-1px);
}
</style>
