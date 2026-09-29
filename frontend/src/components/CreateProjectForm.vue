<script setup>
import { ref } from 'vue'

const props = defineProps({
  createProject: { type: Function, required: true },
})
const emit = defineEmits(['created'])

const name = ref('')
const scope = ref('')
const budget = ref('')
const error = ref('')
const busy = ref(false)

async function onSubmit() {
  error.value = ''
  busy.value = true
  try {
    const project = await props.createProject({
      name: name.value.trim(),
      scope: scope.value.trim(),
      budget: budget.value === '' ? null : String(budget.value),
    })
    emit('created', project)
    name.value = ''
    scope.value = ''
    budget.value = ''
  } catch (err) {
    error.value = err.message || 'Could not create project.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <form class="form" @submit.prevent="onSubmit">
    <h2>New project</h2>
    <label>
      Name
      <input name="name" v-model="name" required />
    </label>
    <label>
      Scope
      <textarea name="scope" v-model="scope" rows="3" required />
    </label>
    <label>
      Budget (optional)
      <input name="budget" type="number" min="0" step="0.01" v-model="budget" />
    </label>
    <p v-if="error" class="error">{{ error }}</p>
    <button type="submit" :disabled="busy">{{ busy ? 'Creating…' : 'Create project' }}</button>
  </form>
</template>

<style scoped>
.form { display: grid; gap: 0.85rem; }
label { display: grid; gap: 0.35rem; font-weight: 600; }
input, textarea, button {
  font: inherit;
  padding: 0.65rem 0.75rem;
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
