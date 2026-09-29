<script setup>
import { ref } from 'vue'

const props = defineProps({
  assign: { type: Function, required: true },
})
const emit = defineEmits(['assigned'])

const name = ref('')
const phone = ref('')
const email = ref('')
const hourlyRate = ref('')
const error = ref('')
const busy = ref(false)

async function onSubmit() {
  error.value = ''
  if (!phone.value && !email.value) {
    error.value = 'Provide a phone or email.'
    return
  }
  busy.value = true
  try {
    const assignment = await props.assign({
      name: name.value.trim(),
      phone: phone.value.trim(),
      email: email.value.trim(),
      hourly_rate: String(hourlyRate.value),
    })
    emit('assigned', assignment)
    name.value = ''
    phone.value = ''
    email.value = ''
    hourlyRate.value = ''
  } catch (err) {
    error.value = err.message || 'Could not assign contractor.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <form class="form" @submit.prevent="onSubmit">
    <h3>Assign contractor</h3>
    <label>
      Name
      <input name="name" v-model="name" required />
    </label>
    <label>
      Phone
      <input name="phone" v-model="phone" />
    </label>
    <label>
      Email
      <input name="email" type="email" v-model="email" />
    </label>
    <label>
      Hourly rate
      <input name="hourly_rate" type="number" min="0.01" step="0.01" v-model="hourlyRate" required />
    </label>
    <p v-if="error" class="error">{{ error }}</p>
    <button type="submit" :disabled="busy">{{ busy ? 'Assigning…' : 'Assign & get link' }}</button>
  </form>
</template>

<style scoped>
.form { display: grid; gap: 0.75rem; }
label { display: grid; gap: 0.3rem; font-weight: 600; font-size: 0.95rem; }
input, button {
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
