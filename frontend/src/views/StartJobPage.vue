<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createContractorApi } from '../api/contractor.js'
import { uploadWithRetry } from '../lib/upload.js'
import StartJobForm from '../components/StartJobForm.vue'

const route = useRoute()
const router = useRouter()
const token = route.params.token
const api = createContractorApi(token)
const openJobs = ref([])
const error = ref('')

onMounted(async () => {
  try {
    const summary = await api.getSummary()
    openJobs.value = summary.open_jobs || []
  } catch (err) {
    error.value = err.message
  }
})

async function submitJob({ label, notes, parent, photos, location, capturedAt }) {
  const job = await api.createJob({
    label,
    notes,
    parent: parent || null,
  })
  for (const photo of photos || []) {
    const form = new FormData()
    form.append('kind', 'before')
    form.append('file', photo, photo.name)
    form.append('captured_at', capturedAt)
    if (location?.location_missing) {
      form.append('location_missing', 'true')
    } else if (location) {
      form.append('latitude', String(location.latitude))
      form.append('longitude', String(location.longitude))
      form.append('location_missing', 'false')
    } else {
      form.append('location_missing', 'true')
    }
    await uploadWithRetry(() => api.uploadPhoto(job.id, form), { retries: 3, delayMs: 300 })
  }
  return job
}

function onSubmitted() {
  router.push(`/c/${token}`)
}
</script>

<template>
  <div>
    <RouterLink class="back" :to="`/c/${token}`">← Back</RouterLink>
    <p v-if="error" class="error">{{ error }}</p>
    <StartJobForm :open-jobs="openJobs" :submit-job="submitJob" @submitted="onSubmitted" />
  </div>
</template>

<style scoped>
.back { display: inline-block; margin-bottom: 1rem; color: #3d5a45; }
.error { color: #8a2f1f; }
</style>
