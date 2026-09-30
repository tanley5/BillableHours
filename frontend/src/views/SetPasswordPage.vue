<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { createClientApi } from '../api/client.js'

const route = useRoute()
const router = useRouter()
const api = createClientApi()
const password = ref('')
const confirm = ref('')
const error = ref('')
const done = ref(false)
const busy = ref(false)
const token = ref('')

onMounted(async () => {
  token.value = String(route.query.token || '')
  await api.ensureCsrf()
  if (!token.value) {
    error.value = 'Missing invite token.'
  }
})

async function onSubmit() {
  error.value = ''
  if (password.value.length < 8) {
    error.value = 'Password must be at least 8 characters.'
    return
  }
  if (password.value !== confirm.value) {
    error.value = 'Passwords do not match.'
    return
  }
  busy.value = true
  try {
    await api.setPassword(token.value, password.value)
    done.value = true
  } catch (err) {
    error.value = err.message || 'Could not set password.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="page">
    <h1>Set your password</h1>
    <p v-if="done">
      Password saved.
      <RouterLink to="/app/login">Log in</RouterLink>
    </p>
    <form v-else class="form" @submit.prevent="onSubmit">
      <label>
        New password
        <input v-model="password" type="password" autocomplete="new-password" required />
      </label>
      <label>
        Confirm password
        <input v-model="confirm" type="password" autocomplete="new-password" required />
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" :disabled="busy || !token">
        {{ busy ? 'Saving…' : 'Save password' }}
      </button>
    </form>
  </main>
</template>

<style scoped>
.page { max-width: 24rem; display: grid; gap: 1rem; }
.form { display: grid; gap: 0.75rem; }
label { display: grid; gap: 0.35rem; font-weight: 600; }
input, button {
  font: inherit;
  padding: 0.7rem 0.75rem;
  border: 1px solid #c5d0c4;
  border-radius: 0.4rem;
}
button {
  background: #1f3d2a;
  color: #f4f7f2;
  border: none;
  font-weight: 700;
}
.error { color: #8a2f1f; margin: 0; }
</style>
