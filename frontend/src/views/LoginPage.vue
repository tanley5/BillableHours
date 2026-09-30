<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createClientApi } from '../api/client.js'
import LoginForm from '../components/LoginForm.vue'

const router = useRouter()
const api = createClientApi()
const checking = ref(true)

function redirectForRole(role) {
  if (role === 'contractor') router.replace('/contractor')
  else router.replace('/app/projects')
}

onMounted(async () => {
  try {
    const me = await api.me()
    redirectForRole(me.role)
  } catch {
    checking.value = false
  }
})

async function login(email, password) {
  return api.login(email, password)
}

function onSuccess(user) {
  redirectForRole(user?.role)
}
</script>

<template>
  <p v-if="checking">Checking session…</p>
  <LoginForm v-else :login="login" @success="onSuccess" />
</template>
