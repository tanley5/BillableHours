<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createContractorApi } from '../api/contractor.js'
import { uploadWithRetry } from '../lib/upload.js'
import FinishJobForm from '../components/FinishJobForm.vue'

const route = useRoute()
const router = useRouter()
const token = route.params.token
const jobId = Number(route.params.jobId)
const api = createContractorApi(token)
const job = ref(null)
const error = ref('')

onMounted(async () => {
  try {
    const summary = await api.getSummary()
    const all = [
      ...(summary.open_jobs || []),
      ...((summary.open_jobs || []).flatMap((j) => j.found_issues || [])),
    ]
    job.value = all.find((j) => j.id === jobId) || { id: jobId, label: `Job #${jobId}`, status: 'open' }
  } catch (err) {
    error.value = err.message
  }
})

async function submitFinish({ notes, photos, location, capturedAt }) {
  if (notes) {
    await api.updateJob(jobId, { notes })
  }
  for (const photo of photos) {
    const form = new FormData()
    form.append('kind', 'after')
    form.append('file', photo, photo.name)
    form.append('captured_at', capturedAt)
    if (location?.location_missing) {
      form.append('location_missing', 'true')
    } else {
      form.append('latitude', String(location.latitude))
      form.append('longitude', String(location.longitude))
      form.append('location_missing', 'false')
    }
    await uploadWithRetry(() => api.uploadPhoto(jobId, form), { retries: 3, delayMs: 300 })
  }
  return { id: jobId }
}

function onSubmitted() {
  router.push(`/c/${token}`)
}
</script>

<template>
  <div>
    <RouterLink class="back" :to="`/c/${token}`">← Back</RouterLink>
    <p v-if="error" class="error">{{ error }}</p>
    <FinishJobForm v-if="job" :job="job" :submit-finish="submitFinish" @submitted="onSubmitted" />
  </div>
</template>

<style scoped>
.back { display: inline-block; margin-bottom: 1rem; color: #3d5a45; }
.error { color: #8a2f1f; }
</style>
