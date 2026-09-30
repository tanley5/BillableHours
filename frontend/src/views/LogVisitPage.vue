<script setup>
import { useRoute, useRouter } from 'vue-router'
import { createContractorApi } from '../api/contractor.js'
import LogVisitForm from '../components/LogVisitForm.vue'

const route = useRoute()
const router = useRouter()
const assignmentId = route.params.assignmentId
const api = createContractorApi(assignmentId)

async function submitVisit(payload) {
  return api.createVisit(payload)
}

function onSubmitted() {
  router.push(`/contractor/assignments/${assignmentId}`)
}
</script>

<template>
  <div>
    <RouterLink class="back" :to="`/contractor/assignments/${assignmentId}`">← Back</RouterLink>
    <LogVisitForm :submit-visit="submitVisit" @submitted="onSubmitted" />
  </div>
</template>

<style scoped>
.back { display: inline-block; margin-bottom: 1rem; color: #3d5a45; }
</style>
