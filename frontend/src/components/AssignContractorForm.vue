<script setup>
import { onMounted, ref } from 'vue'

const props = defineProps({
  assign: { type: Function, required: true },
  listContractors: { type: Function, required: true },
})
const emit = defineEmits(['assigned'])

const contractors = ref([])
const contractorId = ref('')
const hourlyRate = ref('')
const error = ref('')
const busy = ref(false)

onMounted(async () => {
  try {
    contractors.value = await props.listContractors()
  } catch (err) {
    error.value = err.message || 'Could not load contractors.'
  }
})

async function onSubmit() {
  error.value = ''
  if (!contractorId.value) {
    error.value = 'Select a contractor from your pool.'
    return
  }
  busy.value = true
  try {
    const assignment = await props.assign({
      contractor_id: Number(contractorId.value),
      hourly_rate: String(hourlyRate.value),
    })
    emit('assigned', assignment)
    contractorId.value = ''
    hourlyRate.value = ''
  } catch (err) {
    error.value = err.message || 'Could not assign contractor.'
  } finally {
    busy.value = false
  }
}

function labelFor(c) {
  const connect = c.connect_status === 'complete' ? 'Connect ready' : `Connect: ${c.connect_status}`
  return `${c.name} (${connect})`
}
</script>

<template>
  <form class="form" @submit.prevent="onSubmit">
    <h3>Assign contractor</h3>
    <p class="hint">Only contractors with completed Connect can be assigned.</p>
    <label>
      Contractor
      <select name="contractor_id" v-model="contractorId" required>
        <option disabled value="">Select…</option>
        <option v-for="c in contractors" :key="c.id" :value="String(c.id)">
          {{ labelFor(c) }}
        </option>
      </select>
    </label>
    <label>
      Hourly rate
      <input name="hourly_rate" type="number" min="0.01" step="0.01" v-model="hourlyRate" required />
    </label>
    <p v-if="error" class="error">{{ error }}</p>
    <button type="submit" :disabled="busy">{{ busy ? 'Assigning…' : 'Send invite' }}</button>
  </form>
</template>

<style scoped>
.form { display: grid; gap: 0.75rem; }
.hint { margin: 0; color: #5c6b5a; font-size: 0.9rem; }
label { display: grid; gap: 0.3rem; font-weight: 600; font-size: 0.95rem; }
input, select, button {
  font: inherit;
  padding: 0.6rem 0.7rem;
  border: 1px solid #c5d0c4;
  border-radius: 0.4rem;
}
button {
  background: #3d5a45;
  color: #f4f7f2;
  border: none;
  font-weight: 700;
}
.error { color: #8a2f1f; margin: 0; }
</style>
