<script setup>
import { ref } from 'vue'
import { preparePhotos } from '../lib/photos.js'
import { captureLocation } from '../lib/geo.js'

const props = defineProps({
  job: { type: Object, required: true },
  submitFinish: { type: Function, required: true },
})
const emit = defineEmits(['submitted'])

const notes = ref('')
const files = ref(null)
const error = ref('')
const busy = ref(false)

async function onSubmit() {
  error.value = ''
  const fileList = files.value?.files ? Array.from(files.value.files) : []
  if (!fileList.length) {
    error.value = 'Add at least one after photo to finish the job.'
    return
  }
  busy.value = true
  try {
    const prepared = await preparePhotos(fileList)
    const location = await captureLocation()
    const capturedAt = new Date().toISOString()
    const job = await props.submitFinish({
      notes: notes.value,
      photos: prepared,
      location,
      capturedAt,
    })
    emit('submitted', job)
  } catch (err) {
    error.value = err.message || 'Could not finish job.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <form class="form" @submit.prevent="onSubmit">
    <h1>Finish {{ job.label }}</h1>
    <p class="hint">Location is recorded at photo time. Adding the first after photo marks the job complete.</p>

    <label>
      After photos
      <input
        ref="files"
        type="file"
        accept="image/*"
        capture="environment"
        multiple
      />
    </label>

    <label>
      Notes (optional)
      <textarea name="notes" v-model="notes" rows="3" />
    </label>

    <p v-if="error" class="error">{{ error }}</p>
    <button type="submit" :disabled="busy">{{ busy ? 'Uploading…' : 'Finish job' }}</button>
  </form>
</template>

<style scoped>
.form { display: grid; gap: 1rem; }
.hint { margin: 0; color: #445044; font-size: 0.95rem; }
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
