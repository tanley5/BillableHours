<script setup>
import { onMounted, ref } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { createClientApi } from '../api/client.js'

const router = useRouter()
const api = createClientApi()
const contractors = ref([])
const error = ref('')
const message = ref('')
const loading = ref(true)
const busy = ref(false)

const name = ref('')
const email = ref('')
const phone = ref('')

async function load() {
  contractors.value = await api.listContractors()
}

onMounted(async () => {
  try {
    await api.me()
    await load()
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

async function onCreate() {
  error.value = ''
  message.value = ''
  busy.value = true
  try {
    await api.createContractor({
      name: name.value.trim(),
      email: email.value.trim(),
      phone: phone.value.trim(),
    })
    name.value = ''
    email.value = ''
    phone.value = ''
    message.value = 'Contractor added to your pool.'
    await load()
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

async function resend(id) {
  error.value = ''
  message.value = ''
  try {
    await api.resendContractorInvite(id)
    message.value = 'Invite resent.'
  } catch (err) {
    error.value = err.message
  }
}
</script>

<template>
  <main class="page">
    <RouterLink class="back" to="/app/projects">← Projects</RouterLink>
    <h1>Contractor pool</h1>
    <p class="hint">
      New contractors get a set-password invite. Existing emails are added silently to your roster.
      Connect must be complete before assignment.
    </p>

    <form class="form" @submit.prevent="onCreate">
      <label>Name <input v-model="name" required /></label>
      <label>Email <input v-model="email" type="email" required /></label>
      <label>Phone <input v-model="phone" /></label>
      <button type="submit" :disabled="busy">{{ busy ? 'Adding…' : 'Add contractor' }}</button>
    </form>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="message" class="ok">{{ message }}</p>
    <p v-if="loading">Loading…</p>
    <ul v-else class="list">
      <li v-for="c in contractors" :key="c.id">
        <div>
          <strong>{{ c.name }}</strong>
          <span class="muted"> · {{ c.email }}</span>
        </div>
        <div class="meta">
          <span>Connect: {{ c.connect_status }}</span>
          <span>{{ c.activated ? 'Activated' : 'Pending password' }}</span>
          <button
            v-if="!c.activated"
            type="button"
            class="linkish"
            @click="resend(c.id)"
          >
            Resend invite
          </button>
        </div>
      </li>
      <li v-if="!contractors.length" class="empty">No contractors yet.</li>
    </ul>
  </main>
</template>

<style scoped>
.page { display: grid; gap: 1rem; }
.back { color: #3d5a45; }
.hint { color: #445044; margin: 0; }
.form { display: grid; gap: 0.65rem; max-width: 24rem; }
label { display: grid; gap: 0.3rem; font-weight: 600; }
input, button {
  font: inherit;
  padding: 0.6rem 0.7rem;
  border: 1px solid #c5d0c4;
  border-radius: 0.4rem;
}
button {
  background: #1f3d2a;
  color: #f4f7f2;
  border: none;
  font-weight: 700;
}
.list { list-style: none; padding: 0; margin: 0; display: grid; gap: 0.85rem; }
.meta { display: flex; gap: 0.85rem; flex-wrap: wrap; color: #5c6b5a; font-size: 0.9rem; }
.linkish {
  background: none;
  border: none;
  color: #3d5a45;
  text-decoration: underline;
  padding: 0;
  font: inherit;
  cursor: pointer;
}
.error { color: #8a2f1f; }
.ok { color: #1f3d2a; }
.muted, .empty { color: #5c6b5a; }
</style>
