<script setup>
import { onMounted, ref } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { createContractorSessionApi } from '../api/contractor.js'

const router = useRouter()
const api = createContractorSessionApi()
const me = ref(null)
const error = ref('')
const message = ref('')
const busy = ref(false)

onMounted(async () => {
  try {
    await api.ensureCsrf()
    me.value = await api.me()
  } catch (err) {
    if (err.status === 401 || err.status === 403) {
      router.replace('/app/login')
      return
    }
    error.value = err.message
  }
})

async function startOnboarding() {
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    const result = await api.startConnect()
    if (result.url) {
      window.location.href = result.url
      return
    }
    message.value = `Status: ${result.connect_status}`
    me.value = await api.me()
  } catch (err) {
    error.value = err.message || 'Could not start Connect onboarding.'
  } finally {
    busy.value = false
  }
}

async function refresh() {
  me.value = await api.me()
  message.value = 'Status refreshed.'
}
</script>

<template>
  <main class="page">
    <RouterLink class="back" to="/contractor">← Assignments</RouterLink>
    <h1>Stripe Connect</h1>
    <p>
      Complete Connect onboarding before a client can assign you to a project.
    </p>
    <p v-if="me?.contractor">
      Current status: <strong>{{ me.contractor.connect_status }}</strong>
    </p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="message" class="ok">{{ message }}</p>
    <div class="actions">
      <button type="button" :disabled="busy" @click="startOnboarding">
        {{ busy ? 'Starting…' : 'Start / continue onboarding' }}
      </button>
      <button type="button" class="secondary" @click="refresh">Refresh status</button>
    </div>
  </main>
</template>

<style scoped>
.page { display: grid; gap: 0.75rem; max-width: 28rem; }
.back { color: #3d5a45; }
.actions { display: flex; gap: 0.75rem; flex-wrap: wrap; }
button {
  font: inherit;
  padding: 0.7rem 1rem;
  border: none;
  border-radius: 0.4rem;
  background: #1f3d2a;
  color: #f4f7f2;
  font-weight: 700;
}
button.secondary { background: #3d5a45; }
.error { color: #8a2f1f; }
.ok { color: #1f3d2a; }
</style>
