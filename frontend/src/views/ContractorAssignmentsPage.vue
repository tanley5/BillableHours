<script setup>
import { onMounted, ref } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { createContractorSessionApi } from '../api/contractor.js'

const router = useRouter()
const api = createContractorSessionApi()
const assignments = ref([])
const me = ref(null)
const error = ref('')
const loading = ref(true)

onMounted(async () => {
  try {
    await api.ensureCsrf()
    me.value = await api.me()
    assignments.value = await api.listAssignments()
  } catch (err) {
    if (err.status === 401 || err.status === 403) {
      router.replace('/app/login')
      return
    }
    error.value = err.message
  } finally {
    loading.value = false
  }
})

async function logout() {
  await api.logout()
  router.push('/app/login')
}
</script>

<template>
  <main class="page">
    <header class="top">
      <div>
        <p class="eyebrow">Contractor</p>
        <h1>{{ me?.contractor?.name || 'Assignments' }}</h1>
      </div>
      <div class="links">
        <RouterLink to="/contractor/connect">Stripe Connect</RouterLink>
        <button type="button" class="linkish" @click="logout">Log out</button>
      </div>
    </header>

    <p v-if="me?.contractor" class="connect">
      Connect status:
      <strong>{{ me.contractor.connect_status }}</strong>
    </p>

    <p v-if="loading">Loading…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <ul v-else class="list">
      <li v-for="a in assignments" :key="a.id">
        <RouterLink :to="`/contractor/assignments/${a.id}`">
          {{ a.project_name }}
        </RouterLink>
        <span class="status">{{ a.status }}</span>
      </li>
      <li v-if="!assignments.length" class="empty">No assignments yet.</li>
    </ul>
  </main>
</template>

<style scoped>
.page { display: grid; gap: 1rem; }
.top { display: flex; justify-content: space-between; gap: 1rem; align-items: start; }
.eyebrow { margin: 0; text-transform: uppercase; letter-spacing: 0.06em; font-size: 0.75rem; color: #5c6b5a; }
h1 { margin: 0.25rem 0 0; }
.links { display: flex; gap: 1rem; align-items: center; }
.linkish {
  background: none;
  border: none;
  color: #3d5a45;
  font: inherit;
  cursor: pointer;
  text-decoration: underline;
}
.list { list-style: none; padding: 0; margin: 0; display: grid; gap: 0.75rem; }
.list a { color: #1f3d2a; font-weight: 700; }
.status { margin-left: 0.75rem; color: #5c6b5a; font-size: 0.9rem; }
.connect, .empty { color: #445044; }
.error { color: #8a2f1f; }
</style>
