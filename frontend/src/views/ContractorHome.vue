<script setup>
import { onMounted, ref } from 'vue'
import { createContractorApi } from '../api/contractor.js'

const props = defineProps({
  summary: { type: Object, required: true },
  assignmentId: { type: [String, Number], required: true },
})
const emit = defineEmits(['refresh'])

const api = createContractorApi(props.assignmentId)
const subJobs = ref([])
const error = ref('')
const message = ref('')
const busy = ref(false)
const label = ref('')
const beforeFile = ref(null)
const submitHours = ref({})
const submitNotes = ref({})
const afterFile = ref({})

async function loadSubJobs() {
  subJobs.value = await api.listSubJobs()
}

onMounted(async () => {
  try {
    await loadSubJobs()
  } catch (err) {
    error.value = err.message
  }
})

async function inRoute() {
  busy.value = true
  error.value = ''
  try {
    await api.confirmInRoute()
    message.value = 'Marked in route.'
    emit('refresh')
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

async function createSubJob() {
  busy.value = true
  error.value = ''
  try {
    const form = new FormData()
    form.append('label', label.value)
    form.append('before_photo', beforeFile.value)
    await api.createSubJob(form)
    label.value = ''
    beforeFile.value = null
    message.value = 'Sub-job submitted for client approval.'
    await loadSubJobs()
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

async function submitCompletion(subJobId) {
  busy.value = true
  error.value = ''
  try {
    const form = new FormData()
    form.append('hours', submitHours.value[subJobId])
    form.append('notes', submitNotes.value[subJobId] || '')
    form.append('after_photo', afterFile.value[subJobId])
    await api.createSubmission(subJobId, form)
    message.value = 'Completion submitted for review.'
    await loadSubJobs()
    emit('refresh')
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="home">
    <header>
      <p class="eyebrow">{{ summary.contractor?.name }}</p>
      <h1>{{ summary.project.name }}</h1>
      <p class="scope">{{ summary.project.scope }}</p>
    </header>

    <button
      v-if="!summary.assignment?.in_route_at"
      type="button"
      class="btn"
      :disabled="busy"
      data-test="in-route"
      @click="inRoute"
    >
      I'm on my way
    </button>
    <p v-else class="ok">In route confirmed.</p>

    <nav class="actions">
      <RouterLink class="btn" :to="`/contractor/assignments/${assignmentId}/jobs/new`">
        Start a job (legacy)
      </RouterLink>
      <RouterLink class="btn secondary" :to="`/contractor/assignments/${assignmentId}/visits/new`">
        Log a visit (legacy)
      </RouterLink>
    </nav>

    <section>
      <h2>Sub-jobs</h2>
      <form class="create" @submit.prevent="createSubJob">
        <label>Found issue / sub-job label <input v-model="label" required /></label>
        <label>
          Before photo
          <input type="file" accept="image/*" capture required @change="beforeFile = $event.target.files?.[0]" />
        </label>
        <button type="submit" :disabled="busy">Create for approval</button>
      </form>

      <ul class="list">
        <li v-for="sj in subJobs" :key="sj.id">
          <strong>{{ sj.label }}</strong>
          <span class="muted"> · {{ sj.status }}</span>
          <div v-if="sj.status === 'open'" class="submit">
            <input v-model="submitHours[sj.id]" type="number" min="0.01" step="0.01" placeholder="Hours" required />
            <input v-model="submitNotes[sj.id]" placeholder="Notes" />
            <input type="file" accept="image/*" capture @change="afterFile[sj.id] = $event.target.files?.[0]" />
            <button type="button" :disabled="busy" @click="submitCompletion(sj.id)">Submit completion</button>
          </div>
          <ul v-if="sj.submissions?.length" class="subs">
            <li v-for="sub in sj.submissions" :key="sub.id">
              {{ sub.hours }}h · {{ sub.review_status }}
              <span v-if="sub.review_reason"> — {{ sub.review_reason }}</span>
            </li>
          </ul>
        </li>
      </ul>
    </section>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="message" class="ok">{{ message }}</p>

    <section>
      <h2>Open jobs (legacy)</h2>
      <ul v-if="summary.open_jobs?.length" class="list">
        <li v-for="job in summary.open_jobs" :key="job.id">
          <RouterLink :to="`/contractor/assignments/${assignmentId}/jobs/${job.id}/finish`">
            {{ job.label }}
          </RouterLink>
        </li>
      </ul>
      <p v-else class="empty">No open legacy jobs.</p>
    </section>
  </section>
</template>

<style scoped>
.home { display: grid; gap: 1.25rem; }
.eyebrow { margin: 0; text-transform: uppercase; letter-spacing: 0.06em; font-size: 0.75rem; color: #5c6b5a; }
h1 { margin: 0.25rem 0; font-size: 1.75rem; }
.scope { margin: 0; color: #445044; }
.actions { display: flex; gap: 0.75rem; flex-wrap: wrap; }
.btn {
  display: inline-block;
  background: #1f3d2a;
  color: #f4f7f2;
  text-decoration: none;
  padding: 0.75rem 1rem;
  border-radius: 0.4rem;
  font-weight: 600;
  border: none;
  font: inherit;
  cursor: pointer;
}
.btn.secondary { background: #3d5a45; }
.create, .submit { display: grid; gap: 0.4rem; margin: 0.5rem 0; max-width: 22rem; }
.list, .subs { list-style: none; padding: 0; margin: 0.5rem 0 0; display: grid; gap: 0.65rem; }
.muted, .empty { color: #5c6b5a; }
.error { color: #8a2f1f; }
.ok { color: #1f3d2a; }
input, button { font: inherit; padding: 0.5rem 0.6rem; border-radius: 0.35rem; border: 1px solid #c5d0c4; }
button { background: #1f3d2a; color: #f4f7f2; border: none; font-weight: 700; }
</style>
