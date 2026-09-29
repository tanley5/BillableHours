<script setup>
import { ref } from 'vue'

const props = defineProps({
  kind: { type: String, required: true },
  item: { type: Object, required: true },
  resubmit: { type: Function, required: true },
})
const emit = defineEmits(['submitted'])

const label = ref(props.item.label || '')
const date = ref(props.item.date || '')
const hours = ref(props.item.hours != null ? String(props.item.hours) : '')
const notes = ref(props.item.notes || '')
const error = ref('')
const busy = ref(false)

async function onSubmit() {
  error.value = ''
  busy.value = true
  try {
    const payload =
      props.kind === 'visit'
        ? { date: date.value, hours: String(hours.value), notes: notes.value }
        : { label: label.value, notes: notes.value }
    const result = await props.resubmit(payload)
    emit('submitted', result)
  } catch (err) {
    error.value = err.message || 'Could not resubmit.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <form class="form" @submit.prevent="onSubmit">
    <h1>Respond to dispute</h1>
    <p class="comment">{{ item.client_comment }}</p>

    <template v-if="kind === 'visit'">
      <label>
        Date
        <input name="date" type="date" v-model="date" />
      </label>
      <label>
        Hours
        <input name="hours" type="number" min="0.01" max="16" step="0.01" v-model="hours" />
      </label>
    </template>
    <template v-else>
      <label>
        Label
        <input name="label" v-model="label" />
      </label>
    </template>

    <label>
      Notes
      <textarea name="notes" v-model="notes" rows="3" />
    </label>

    <p v-if="error" class="error">{{ error }}</p>
    <button type="submit" :disabled="busy">{{ busy ? 'Sending…' : 'Resubmit' }}</button>
  </form>
</template>

<style scoped>
.form { display: grid; gap: 1rem; }
.comment {
  margin: 0;
  padding: 0.75rem;
  background: #f7ebe6;
  color: #6b3b2a;
  border-radius: 0.4rem;
}
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
