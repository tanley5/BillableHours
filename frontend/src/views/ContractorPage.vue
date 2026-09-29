<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { createContractorApi } from '../api/contractor.js'
import ContractorHome from './ContractorHome.vue'

const route = useRoute()
const token = route.params.token
const api = createContractorApi(token)
const summary = ref(null)
const error = ref('')
const loading = ref(true)

onMounted(async () => {
  try {
    summary.value = await api.getSummary()
  } catch (err) {
    error.value = err.message || 'Could not load project.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <p v-if="loading">Loading…</p>
  <p v-else-if="error" class="error">{{ error }}</p>
  <ContractorHome v-else :summary="summary" :token="token" />
</template>

<style scoped>
.error { color: #8a2f1f; }
</style>
