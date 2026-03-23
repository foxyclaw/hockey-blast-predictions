<template>
  <div class="text-xs text-base-content/60" :title="skill !== null && skill !== undefined ? `Skill rating: ${Math.round(skill)} — lower = stronger` : 'Skill rating: N/A — no data'">
    <span v-if="skill !== null && skill !== undefined && skill > 0">Skill: {{ Math.round(skill) }}</span>
    <span v-else>Skill: N/A</span>
  </div>
</template>

<script setup>
defineProps({
  skill: {
    type: Number,
    default: null,
  },
})
</script>
