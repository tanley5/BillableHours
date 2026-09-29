<script setup>
import { ref } from 'vue'

const props = defineProps({
  login: { type: Function, required: true },
})
const emit = defineEmits(['success'])

const email = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function onSubmit() {
  error.value = ''
  busy.value = true
  try {
    await props.login(email.value, password.value)
    emit('success')
  } catch (err) {
    error.value = err.message || 'Login failed.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <form class="form" @submit.prevent="onSubmit">
    <h1>Client login</h1>
    <label>
      Email
      <input name="email" type="email" v-model="email" autocomplete="username" required />
    </label>
    <label>
      Password
      <input name="password" type="password" v-model="password" autocomplete="current-password" required />
    </label>
    <p v-if="error" class="error">{{ error }}</p>
    <button type="submit" :disabled="busy">{{ busy ? 'Signing in…' : 'Sign in' }}</button>
  </form>
</template>

<style scoped>
.form { display: grid; gap: 1rem; max-width: 24rem; }
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
