<script setup>
import { useRoute, useRouter } from 'vue-router'
import { createContractorApi } from '../api/contractor.js'
import LogVisitForm from '../components/LogVisitForm.vue'

const route = useRoute()
const router = useRouter()
const token = route.params.token
const api = createContractorApi(token)

async function submitVisit(payload) {
  return api.createVisit(payload)
}

function onSubmitted() {
  router.push(`/c/${token}`)
}
</script>

<template>
  <div>
    <RouterLink class="back" :to="`/c/${token}`">← Back</RouterLink>
    <LogVisitForm :submit-visit="submitVisit" @submitted="onSubmitted" />
  </div>
</template>

<style scoped>
.back { display: inline-block; margin-bottom: 1rem; color: #3d5a45; }
</style>
