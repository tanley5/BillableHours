<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { createContractorApi } from '../api/contractor.js'
import ContractorHome from './ContractorHome.vue'

const route = useRoute()
const router = useRouter()
const assignmentId = route.params.assignmentId
const api = createContractorApi(assignmentId)
const summary = ref(null)
const error = ref('')
const loading = ref(true)
const busy = ref(false)

async function load() {
  summary.value = await api.getSummary()
}

onMounted(async () => {
  try {
    await api.ensureCsrf()
    await load()
  } catch (err) {
    if (err.status === 401 || err.status === 403) {
      router.replace('/app/login')
      return
    }
    error.value = err.message || 'Could not load assignment.'
  } finally {
    loading.value = false
  }
})

async function accept() {
  busy.value = true
  error.value = ''
  try {
    await api.accept()
    await load()
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

async function reject() {
  busy.value = true
  error.value = ''
  try {
    await api.reject()
    router.push('/contractor')
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div>
    <RouterLink class="back" to="/contractor">← Assignments</RouterLink>
    <p v-if="loading">Loading…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <template v-else-if="summary">
      <section v-if="summary.assignment?.status === 'invited'" class="invite">
        <h1>Assignment invite</h1>
        <p>{{ summary.project.name }}</p>
        <p class="muted">{{ summary.project.scope }}</p>
        <div class="actions">
          <button type="button" :disabled="busy" @click="accept">Accept</button>
          <button type="button" class="secondary" :disabled="busy" @click="reject">Reject</button>
        </div>
      </section>
      <ContractorHome
        v-else-if="summary.assignment?.status === 'accepted'"
        :summary="summary"
        :assignment-id="assignmentId"
      />
      <p v-else class="muted">This assignment is {{ summary.assignment?.status }}.</p>
    </template>
  </div>
</template>

<style scoped>
.back { display: inline-block; margin-bottom: 1rem; color: #3d5a45; }
.error { color: #8a2f1f; }
.invite { display: grid; gap: 0.75rem; }
.actions { display: flex; gap: 0.75rem; }
button {
  font: inherit;
  padding: 0.7rem 1rem;
  border: none;
  border-radius: 0.4rem;
  background: #1f3d2a;
  color: #f4f7f2;
  font-weight: 700;
}
button.secondary { background: #6b4a3a; }
.muted { color: #5c6b5a; }
</style>
