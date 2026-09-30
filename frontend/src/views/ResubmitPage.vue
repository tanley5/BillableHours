<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createContractorApi } from '../api/contractor.js'
import ResubmitForm from '../components/ResubmitForm.vue'

const props = defineProps({
  kind: { type: String, required: true },
})

const route = useRoute()
const router = useRouter()
const assignmentId = route.params.assignmentId
const api = createContractorApi(assignmentId)
const item = ref(null)
const error = ref('')

onMounted(async () => {
  try {
    const summary = await api.getSummary()
    if (props.kind === 'job') {
      const id = Number(route.params.jobId)
      item.value = (summary.disputed_jobs || []).find((j) => j.id === id)
    } else {
      const id = Number(route.params.visitId)
      item.value = (summary.disputed_visits || []).find((v) => v.id === id)
    }
    if (!item.value) error.value = 'Disputed item not found.'
  } catch (err) {
    error.value = err.message
  }
})

async function resubmit(payload) {
  if (props.kind === 'job') {
    return api.resubmitJob(item.value.id, payload)
  }
  return api.resubmitVisit(item.value.id, payload)
}

function onSubmitted() {
  router.push(`/contractor/assignments/${assignmentId}`)
}
</script>

<template>
  <div>
    <RouterLink class="back" :to="`/contractor/assignments/${assignmentId}`">← Back</RouterLink>
    <p v-if="error" class="error">{{ error }}</p>
    <ResubmitForm
      v-else-if="item"
      :kind="kind"
      :item="item"
      :resubmit="resubmit"
      @submitted="onSubmitted"
    />
  </div>
</template>

<style scoped>
.back { display: inline-block; margin-bottom: 1rem; color: #3d5a45; }
.error { color: #8a2f1f; }
</style>
