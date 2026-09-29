<script setup>
import { ref } from 'vue'
import { preparePhotos } from '../lib/photos.js'
import { captureLocation } from '../lib/geo.js'

const props = defineProps({
  openJobs: { type: Array, default: () => [] },
  submitJob: { type: Function, required: true },
})

const emit = defineEmits(['submitted'])

const label = ref('')
const parent = ref('')
const notes = ref('')
const files = ref(null)
const error = ref('')
const busy = ref(false)

async function onSubmit() {
  error.value = ''
  if (!label.value.trim()) {
    error.value = 'Label is required.'
    return
  }
  busy.value = true
  try {
    const payload = {
      label: label.value.trim(),
      notes: notes.value,
      parent: parent.value ? Number(parent.value) : null,
    }
    const fileList = files.value?.files ? Array.from(files.value.files) : []
    const prepared = fileList.length ? await preparePhotos(fileList) : []
    const location = prepared.length ? await captureLocation() : null
    const capturedAt = new Date().toISOString()

    const job = await props.submitJob({
      ...payload,
      photos: prepared,
      location,
      capturedAt,
    })
    emit('submitted', job)
  } catch (err) {
    error.value = err.message || 'Could not start job.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <form class="form" @submit.prevent="onSubmit">
    <h1>Start a job</h1>
    <p class="hint">Location is recorded at photo time. If you deny location access, the job still submits with a “no location” flag.</p>

    <label>
      Label
      <input name="label" v-model="label" required autocomplete="off" />
    </label>

    <label>
      Found issue under (optional)
      <select name="parent" v-model="parent">
        <option value="">None — top-level job</option>
        <option v-for="job in openJobs" :key="job.id" :value="String(job.id)">
          {{ job.label }}
        </option>
      </select>
    </label>

    <label>
      Notes
      <textarea name="notes" v-model="notes" rows="3" />
    </label>

    <label>
      Before photos
      <input
        ref="files"
        type="file"
        accept="image/*"
        capture="environment"
        multiple
      />
    </label>

    <p v-if="error" class="error">{{ error }}</p>
    <button type="submit" :disabled="busy">{{ busy ? 'Saving…' : 'Start job' }}</button>
  </form>
</template>

<style scoped>
.form { display: grid; gap: 1rem; }
.hint { margin: 0; color: #445044; font-size: 0.95rem; }
label { display: grid; gap: 0.35rem; font-weight: 600; }
input, select, textarea, button {
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
