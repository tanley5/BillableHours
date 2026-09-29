<script setup>
import { RouterLink } from 'vue-router'
</script>

<template>
  <main class="landing">
    <h1>Billable Hours</h1>
    <p>Track contractor visits and photo-backed jobs for a single property project.</p>
    <div class="actions">
      <RouterLink class="btn" to="/app/login">Client dashboard</RouterLink>
    </div>
    <p class="hint">Contractors open the private link the client shares — no install, no account.</p>
  </main>
</template>

<style scoped>
.landing { display: grid; gap: 1rem; padding-top: 1rem; }
h1 { margin: 0; font-size: 2rem; }
p { margin: 0; color: #445044; }
.actions { display: flex; gap: 0.75rem; }
.btn {
  display: inline-block;
  background: #1f3d2a;
  color: #f4f7f2;
  text-decoration: none;
  padding: 0.75rem 1rem;
  border-radius: 0.4rem;
  font-weight: 700;
}
.hint { font-size: 0.95rem; }
</style>
