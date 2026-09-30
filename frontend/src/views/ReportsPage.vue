<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { createClientApi } from '../api/client.js'

const router = useRouter()
const api = createClientApi()
const report = ref(null)
const error = ref('')
const loading = ref(true)

const statusRows = computed(() => {
  const by = report.value?.projects_by_status || {}
  return Object.entries(by).map(([status, count]) => ({ status, count }))
})

onMounted(async () => {
  try {
    await api.me()
    report.value = await api.reportDashboard()
  } catch (err) {
    if (err.status === 403 || err.status === 401) {
      router.replace('/app/login')
      return
    }
    error.value = err.message
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="page" data-test="report-page">
    <header class="top">
      <div>
        <p class="eyebrow">Client</p>
        <h1>Reports</h1>
      </div>
      <RouterLink class="ghost link" to="/app/projects">← Projects</RouterLink>
    </header>

    <p v-if="loading">Loading…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <template v-else-if="report">
      <ul class="metrics">
        <li>
          <h2>Active projects</h2>
          <p data-test="active-projects">{{ report.active_projects }}</p>
        </li>
        <li>
          <h2>Awaiting approval</h2>
          <p data-test="awaiting-approval">{{ report.sub_jobs_awaiting_approval }}</p>
        </li>
        <li>
          <h2>Frozen projects</h2>
          <p data-test="frozen-projects">{{ report.frozen_projects }}</p>
        </li>
        <li>
          <h2>Escrow held</h2>
          <p data-test="escrow-held">${{ report.escrow_held_total }}</p>
        </li>
        <li>
          <h2>Expired / detached</h2>
          <p data-test="escrow-expired">{{ report.escrow_expired_or_detached }}</p>
        </li>
        <li>
          <h2>Platform fees captured</h2>
          <p data-test="fees-captured">${{ report.platform_fees_captured_total }}</p>
        </li>
      </ul>

      <section>
        <h2>Projects by status</h2>
        <ul class="status-list" data-test="status-breakdown">
          <li v-for="row in statusRows" :key="row.status">
            <span>{{ row.status }}</span>
            <strong>{{ row.count }}</strong>
          </li>
        </ul>
      </section>
    </template>
  </section>
</template>

<style scoped>
.page { display: grid; gap: 1.5rem; }
.top { display: flex; justify-content: space-between; align-items: start; gap: 1rem; }
.eyebrow { margin: 0; text-transform: uppercase; letter-spacing: 0.06em; font-size: 0.75rem; color: #5c6b5a; }
h1 { margin: 0.2rem 0; }
h2 { margin: 0 0 0.35rem; font-size: 0.95rem; color: #3d5a45; }
.metrics {
  list-style: none; padding: 0; margin: 0;
  display: grid; gap: 0.75rem;
  grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
}
.metrics li {
  border: 1px solid #c5d0c4;
  border-radius: 0.4rem;
  padding: 0.85rem 1rem;
  background: #f4f7f2;
}
.metrics p { margin: 0; font-size: 1.4rem; font-weight: 700; color: #1f3d2a; }
.status-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 0.4rem; max-width: 24rem; }
.status-list li { display: flex; justify-content: space-between; gap: 1rem; }
.ghost.link { color: #3d5a45; text-decoration: none; font-weight: 600; }
.error { color: #8a2f1f; }
</style>
