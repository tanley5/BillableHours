<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { createClientApi } from '../api/client.js'
import ProjectDashboard from './ProjectDashboard.vue'

const route = useRoute()
const router = useRouter()
const api = createClientApi()
const projectId = Number(route.params.projectId)

const project = ref(null)
const jobs = ref([])
const visits = ref([])
const error = ref('')
const loading = ref(true)

async function load() {
  error.value = ''
  const [p, j, v] = await Promise.all([
    api.getProject(projectId),
    api.listJobs(projectId),
    api.listVisits(projectId),
  ])
  project.value = p
  jobs.value = j
  visits.value = v
}

onMounted(async () => {
  try {
    await api.me()
    await load()
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

async function refresh() {
  try {
    await load()
  } catch (err) {
    error.value = err.message
  }
}
</script>

<template>
  <div>
    <RouterLink class="back" to="/app/projects">← All projects</RouterLink>
    <p v-if="loading">Loading…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <ProjectDashboard
      v-else-if="project"
      :project="project"
      :jobs="jobs"
      :visits="visits"
      :on-approve-job="(id) => api.approveJob(id)"
      :on-dispute-job="(id, comment) => api.disputeJob(id, comment)"
      :on-approve-visit="(id) => api.approveVisit(id)"
      :on-dispute-visit="(id, comment) => api.disputeVisit(id, comment)"
      :on-cancel="(id) => api.cancelAssignment(id)"
      :on-assign="(payload) => api.createAssignment(projectId, payload)"
      :list-contractors="(projectId) => api.listContractors(projectId)"
      :export-url="api.exportUrl(projectId)"
      @refresh="refresh"
    />
  </div>
</template>

<style scoped>
.back { display: inline-block; margin-bottom: 1rem; color: #3d5a45; }
.error { color: #8a2f1f; }
</style>
