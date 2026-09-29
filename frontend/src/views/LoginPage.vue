<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createClientApi } from '../api/client.js'
import LoginForm from '../components/LoginForm.vue'

const router = useRouter()
const api = createClientApi()
const checking = ref(true)

onMounted(async () => {
  try {
    await api.me()
    router.replace('/app/projects')
  } catch {
    checking.value = false
  }
})

async function login(email, password) {
  return api.login(email, password)
}

function onSuccess() {
  router.push('/app/projects')
}
</script>

<template>
  <p v-if="checking">Checking session…</p>
  <LoginForm v-else :login="login" @success="onSuccess" />
</template>
