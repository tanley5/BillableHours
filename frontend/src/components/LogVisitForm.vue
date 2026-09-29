<script setup>
import { ref } from 'vue'

const props = defineProps({
  submitVisit: { type: Function, required: true },
})
const emit = defineEmits(['submitted'])

const date = ref(new Date().toISOString().slice(0, 10))
const hours = ref('')
const notes = ref('')
const error = ref('')
const busy = ref(false)

async function onSubmit() {
  error.value = ''
  const value = Number(hours.value)
  if (!date.value) {
    error.value = 'Date is required.'
    return
  }
  if (!Number.isFinite(value) || value <= 0) {
    error.value = 'Hours must be greater than 0.'
    return
  }
  if (value > 16) {
    error.value = 'Hours cannot exceed 16.'
    return
  }
  busy.value = true
  try {
    const visit = await props.submitVisit({
      date: date.value,
      hours: String(hours.value),
      notes: notes.value,
    })
    emit('submitted', visit)
  } catch (err) {
    error.value = err.message || 'Could not log visit.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <form class="form" @submit.prevent="onSubmit">
    <h1>Log a visit</h1>

    <label>
      Date
      <input name="date" type="date" v-model="date" required />
    </label>

    <label>
      Hours
      <input name="hours" type="number" min="0.01" max="16" step="0.01" v-model="hours" required />
    </label>

    <label>
      Notes
      <textarea name="notes" v-model="notes" rows="3" />
    </label>

    <p v-if="error" class="error">{{ error }}</p>
    <button type="submit" :disabled="busy">{{ busy ? 'Saving…' : 'Log visit' }}</button>
  </form>
</template>

<style scoped>
.form { display: grid; gap: 1rem; }
label { display: grid; gap: 0.35rem; font-weight: 600; }
input, textarea, button {
  font: inherit;
  padding: 0.7rem 0.75rem;
  border: 1px solid #c5d0c4;
  border-radius: 0.4rem;
}
button {
  background: #1f3d2a;
  color: #f4f7f2;
  border: none;
  font-weight: 700;
}
.error { color: #8a2f1f; margin: 0; }
</style>
