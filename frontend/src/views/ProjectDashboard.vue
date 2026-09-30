<script setup>
import { computed, reactive, ref } from 'vue'
import DragAssignBoard from '../components/DragAssignBoard.vue'

const props = defineProps({
  project: { type: Object, required: true },
  jobs: { type: Array, default: () => [] },
  visits: { type: Array, default: () => [] },
  onApproveJob: { type: Function, required: true },
  onDisputeJob: { type: Function, required: true },
  onApproveVisit: { type: Function, required: true },
  onDisputeVisit: { type: Function, required: true },
  onCancel: { type: Function, required: true },
  onAssign: { type: Function, required: true },
  listContractors: { type: Function, required: true },
  exportUrl: { type: String, required: true },
})

const emit = defineEmits(['refresh'])

const selectedJobs = reactive({})
const selectedVisits = reactive({})
const disputeTarget = ref(null)
const disputeComment = ref('')
const message = ref('')
const error = ref('')
const busy = ref(false)

const totals = computed(() => props.project.totals || {})

function isSelectableJob(job) {
  return job.status === 'complete'
}

function isSelectableVisit(visit) {
  return visit.status === 'pending'
}

async function run(action) {
  error.value = ''
  message.value = ''
  busy.value = true
  try {
    await action()
    emit('refresh')
  } catch (err) {
    error.value = err.message || 'Action failed.'
  } finally {
    busy.value = false
  }
}

function startDispute(kind, id) {
  disputeTarget.value = { kind, id }
  disputeComment.value = ''
}

async function confirmDispute() {
  if (!disputeTarget.value) return
  const comment = disputeComment.value.trim()
  if (!comment) {
    error.value = 'A comment is required to dispute.'
    return
  }
  const { kind, id } = disputeTarget.value
  await run(async () => {
    if (kind === 'job') await props.onDisputeJob(id, comment)
    else await props.onDisputeVisit(id, comment)
    disputeTarget.value = null
    disputeComment.value = ''
  })
}

async function bulkApprove() {
  const jobIds = Object.entries(selectedJobs)
    .filter(([, on]) => on)
    .map(([id]) => Number(id))
  const visitIds = Object.entries(selectedVisits)
    .filter(([, on]) => on)
    .map(([id]) => Number(id))
  await run(async () => {
    for (const id of jobIds) await props.onApproveJob(id)
    for (const id of visitIds) await props.onApproveVisit(id)
    Object.keys(selectedJobs).forEach((k) => delete selectedJobs[k])
    Object.keys(selectedVisits).forEach((k) => delete selectedVisits[k])
  })
}

async function assign(payload) {
  return props.onAssign(payload)
}

function onAssigned(assignment) {
  message.value = `Invited ${assignment.contractor?.name || 'contractor'}.`
  emit('refresh')
}

function onSaved() {
  emit('refresh')
}
</script>

<template>
  <section class="dashboard">
    <header>
      <p class="eyebrow">Project</p>
      <h1>{{ project.name }}</h1>
      <p class="scope">{{ project.scope }}</p>
      <p v-if="project.budget" class="budget">Budget: ${{ project.budget }}</p>
    </header>

    <section class="totals" aria-label="Totals">
      <div>
        <h2>Approved</h2>
        <p>{{ totals.approved_hours }} h · ${{ totals.approved_cost }}</p>
      </div>
      <div>
        <h2>Pending</h2>
        <p>{{ totals.pending_hours }} h · ${{ totals.pending_cost }}</p>
      </div>
    </section>

    <p v-if="message" class="ok">{{ message }}</p>
    <p v-if="error" class="error">{{ error }}</p>

    <section class="toolbar">
      <button
        type="button"
        data-test="bulk-approve"
        :disabled="busy"
        @click="bulkApprove"
      >
        Bulk approve selected
      </button>
      <a data-test="export-csv" class="export" :href="exportUrl">Export approved CSV</a>
    </section>

    <section>
      <h2>Contractors</h2>
      <ul class="list">
        <li v-for="a in project.assignments || []" :key="a.id">
          <div>
            <strong>{{ a.contractor.name }}</strong>
            <span class="muted"> · ${{ a.hourly_rate }}/hr · {{ a.status }}</span>
          </div>
          <div class="row-actions" v-if="a.status === 'invited'">
            <button
              type="button"
              class="danger"
              :data-test="`cancel-${a.id}`"
              :disabled="busy"
              @click="run(() => onCancel(a.id))"
            >
              Cancel invite
            </button>
          </div>
        </li>
      </ul>
      <DragAssignBoard
        :project-id="project.id"
        :assignments="project.assignments || []"
        :assign="assign"
        :list-contractors="listContractors"
        @assigned="onAssigned"
        @saved="onSaved"
      />
    </section>

    <section>
      <h2>Jobs</h2>
      <ul class="list jobs">
        <li v-for="job in jobs" :key="job.id" class="job">
          <div class="job-head">
            <label v-if="isSelectableJob(job)" class="select">
              <input
                type="checkbox"
                :data-test="`select-job-${job.id}`"
                v-model="selectedJobs[job.id]"
              />
              Select
            </label>
            <strong>{{ job.label }}</strong>
            <span class="badge">{{ job.status }}</span>
          </div>

          <div class="timeline">
            <figure v-for="photo in job.photos || []" :key="photo.id">
              <img :src="photo.url" :alt="`${photo.kind} photo`" />
              <figcaption>
                {{ photo.kind }}
                <span v-if="photo.location_missing" class="warn-text">no location</span>
              </figcaption>
            </figure>
          </div>

          <div class="row-actions" v-if="job.status === 'complete'">
            <button
              type="button"
              :data-test="`approve-job-${job.id}`"
              :disabled="busy"
              @click="run(() => onApproveJob(job.id))"
            >
              Approve
            </button>
            <button
              type="button"
              class="danger"
              :data-test="`dispute-job-${job.id}`"
              :disabled="busy"
              @click="startDispute('job', job.id)"
            >
              Dispute
            </button>
          </div>

          <ul v-if="job.found_issues?.length" class="found">
            <li v-for="issue in job.found_issues" :key="issue.id">
              <div class="job-head">
                <label v-if="isSelectableJob(issue)" class="select">
                  <input
                    type="checkbox"
                    :data-test="`select-job-${issue.id}`"
                    v-model="selectedJobs[issue.id]"
                  />
                  Select
                </label>
                <strong>{{ issue.label }}</strong>
                <span class="badge">Found issue</span>
                <span class="badge">{{ issue.status }}</span>
              </div>
              <div class="timeline">
                <figure v-for="photo in issue.photos || []" :key="photo.id">
                  <img :src="photo.url" :alt="`${photo.kind} photo`" />
                  <figcaption>
                    {{ photo.kind }}
                    <span v-if="photo.location_missing" class="warn-text">no location</span>
                  </figcaption>
                </figure>
              </div>
              <div class="row-actions" v-if="issue.status === 'complete'">
                <button
                  type="button"
                  :data-test="`approve-job-${issue.id}`"
                  :disabled="busy"
                  @click="run(() => onApproveJob(issue.id))"
                >
                  Approve
                </button>
                <button
                  type="button"
                  class="danger"
                  :data-test="`dispute-job-${issue.id}`"
                  :disabled="busy"
                  @click="startDispute('job', issue.id)"
                >
                  Dispute
                </button>
              </div>
            </li>
          </ul>
        </li>
      </ul>
    </section>

    <section>
      <h2>Visits</h2>
      <ul class="list">
        <li v-for="visit in visits" :key="visit.id">
          <div class="job-head">
            <label v-if="isSelectableVisit(visit)" class="select">
              <input
                type="checkbox"
                :data-test="`select-visit-${visit.id}`"
                v-model="selectedVisits[visit.id]"
              />
              Select
            </label>
            <strong>{{ visit.date }}</strong>
            <span>{{ visit.hours }}h</span>
            <span class="badge">{{ visit.status }}</span>
          </div>
          <p v-if="visit.notes" class="notes">{{ visit.notes }}</p>
          <div class="row-actions" v-if="visit.status === 'pending'">
            <button
              type="button"
              :data-test="`approve-visit-${visit.id}`"
              :disabled="busy"
              @click="run(() => onApproveVisit(visit.id))"
            >
              Approve
            </button>
            <button
              type="button"
              class="danger"
              :data-test="`dispute-visit-${visit.id}`"
              :disabled="busy"
              @click="startDispute('visit', visit.id)"
            >
              Dispute
            </button>
          </div>
        </li>
      </ul>
    </section>

    <div v-if="disputeTarget" class="dispute-panel">
      <h3>Dispute comment</h3>
      <textarea name="dispute-comment" v-model="disputeComment" rows="3" />
      <button type="button" data-test="confirm-dispute" :disabled="busy" @click="confirmDispute">
        Confirm dispute
      </button>
    </div>
  </section>
</template>

<style scoped>
.dashboard { display: grid; gap: 1.5rem; }
.eyebrow { margin: 0; text-transform: uppercase; letter-spacing: 0.06em; font-size: 0.75rem; color: #5c6b5a; }
h1 { margin: 0.2rem 0; font-size: 1.8rem; }
.scope, .budget, .notes { margin: 0; color: #445044; }
.totals {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}
.totals > div {
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid #d5e0d3;
  border-radius: 0.5rem;
  padding: 0.85rem 1rem;
}
.totals h2 { margin: 0 0 0.35rem; font-size: 0.95rem; }
.totals p { margin: 0; font-weight: 700; }
.toolbar { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; }
.list { list-style: none; padding: 0; margin: 0 0 1rem; display: grid; gap: 0.85rem; }
.job-head { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }
.select { font-size: 0.85rem; font-weight: 500; display: inline-flex; gap: 0.3rem; align-items: center; }
.badge {
  font-size: 0.75rem;
  background: #e7efe4;
  color: #2d4a34;
  padding: 0.15rem 0.45rem;
  border-radius: 0.25rem;
}
.badge.warn { background: #f7ebe6; color: #6b3b2a; }
.timeline {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(7rem, 1fr));
  gap: 0.5rem;
  margin: 0.65rem 0;
}
.timeline figure { margin: 0; }
.timeline img {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
  border-radius: 0.35rem;
  background: #dfe8dc;
}
.timeline figcaption { font-size: 0.8rem; color: #445044; }
.warn-text { color: #8a2f1f; margin-left: 0.35rem; }
.row-actions { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem; }
.found {
  list-style: none;
  padding: 0.75rem 0 0 0.75rem;
  margin: 0.75rem 0 0;
  border-left: 3px solid #c5d0c4;
  display: grid;
  gap: 0.85rem;
}
button, .export {
  font: inherit;
  padding: 0.55rem 0.8rem;
  border-radius: 0.35rem;
  border: 1px solid #c5d0c4;
  background: #1f3d2a;
  color: #f4f7f2;
  text-decoration: none;
  font-weight: 600;
  cursor: pointer;
}
button.danger { background: #6b3b2a; border-color: #6b3b2a; }
.export { background: #3d5a45; }
.ok { color: #2d4a34; margin: 0; }
.error { color: #8a2f1f; margin: 0; }
.muted { color: #667066; }
.dispute-panel {
  position: sticky;
  bottom: 0.75rem;
  background: #fff8f5;
  border: 1px solid #e2c4b8;
  border-radius: 0.5rem;
  padding: 0.85rem;
  display: grid;
  gap: 0.6rem;
}
.dispute-panel textarea {
  font: inherit;
  padding: 0.6rem;
  border-radius: 0.35rem;
  border: 1px solid #c5d0c4;
}
</style>
