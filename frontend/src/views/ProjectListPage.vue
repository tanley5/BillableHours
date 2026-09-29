<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { createClientApi } from '../api/client.js'
import CreateProjectForm from '../components/CreateProjectForm.vue'

const router = useRouter()
const api = createClientApi()
const projects = ref([])
const error = ref('')
const user = ref(null)

onMounted(async () => {
  try {
    user.value = await api.me()
    projects.value = await api.listProjects()
  } catch (err) {
    if (err.status === 403 || err.status === 401) {
      router.replace('/app/login')
      return
    }
    error.value = err.message
  }
})

async function createProject(payload) {
  const budget =
    payload.budget === null || payload.budget === ''
      ? null
      : payload.budget
  return api.createProject({
    name: payload.name,
    scope: payload.scope,
    budget,
  })
}

function onCreated(project) {
  router.push(`/app/projects/${project.id}`)
}

async function logout() {
  await api.logout()
  router.push('/app/login')
}
</script>

<template>
  <section class="page">
    <header class="top">
      <div>
        <p class="eyebrow">Client</p>
        <h1>Projects</h1>
        <p v-if="user" class="muted">{{ user.email }}</p>
      </div>
      <button type="button" class="ghost" @click="logout">Log out</button>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <ul v-if="projects.length" class="list">
      <li v-for="p in projects" :key="p.id">
        <RouterLink :to="`/app/projects/${p.id}`">{{ p.name }}</RouterLink>
      </li>
    </ul>
    <p v-else class="muted">No projects yet.</p>

    <CreateProjectForm :create-project="createProject" @created="onCreated" />
  </section>
</template>

<style scoped>
.page { display: grid; gap: 1.25rem; }
.top { display: flex; justify-content: space-between; gap: 1rem; align-items: start; }
.eyebrow { margin: 0; text-transform: uppercase; letter-spacing: 0.06em; font-size: 0.75rem; color: #5c6b5a; }
h1 { margin: 0.2rem 0; }
.muted { color: #667066; margin: 0; }
.list { list-style: none; padding: 0; margin: 0; display: grid; gap: 0.5rem; }
.list a { color: #1f3d2a; font-weight: 700; text-decoration: none; font-size: 1.1rem; }
.ghost {
  font: inherit;
  background: transparent;
  border: 1px solid #c5d0c4;
  border-radius: 0.35rem;
  padding: 0.45rem 0.7rem;
  cursor: pointer;
}
.error { color: #8a2f1f; }
</style>
