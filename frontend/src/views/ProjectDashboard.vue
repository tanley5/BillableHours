<script setup>
import { computed, ref } from 'vue'
import DragAssignBoard from '../components/DragAssignBoard.vue'
import SubJobsPanel from '../components/SubJobsPanel.vue'

const props = defineProps({
  project: { type: Object, required: true },
  /** @deprecated SPEC1 — kept for API compat; not shown in SPEC2 polish1 UI */
  jobs: { type: Array, default: () => [] },
  /** @deprecated SPEC1 — kept for API compat; not shown in SPEC2 polish1 UI */
  visits: { type: Array, default: () => [] },
  onApproveJob: { type: Function, required: true },
  onDisputeJob: { type: Function, required: true },
  onApproveVisit: { type: Function, required: true },
  onDisputeVisit: { type: Function, required: true },
  onCancel: { type: Function, required: true },
  onAssign: { type: Function, required: true },
  listContractors: { type: Function, required: true },
  createSubJob: { type: Function, required: true },
  approveSubJob: { type: Function, required: true },
  denySubJob: { type: Function, required: true },
  acceptSubmission: { type: Function, required: true },
  rejectSubmission: { type: Function, required: true },
  reauthorizeEscrow: { type: Function, required: true },
  detachEscrow: { type: Function, required: true },
  loadActivity: { type: Function, required: true },
  exportUrl: { type: String, required: true },
})

const emit = defineEmits(['refresh'])

const message = ref('')
const error = ref('')
const busy = ref(false)

const totals = computed(() => props.project.totals || {})

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
      <p v-if="project.customer_contact" class="budget">Contact: {{ project.customer_contact }}</p>
      <p class="budget">Status: {{ project.status }}<span v-if="project.frozen"> · FROZEN</span></p>
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

    <SubJobsPanel
      :project-id="project.id"
      :project-frozen="!!project.frozen"
      :frozen-reason="project.frozen_reason || ''"
      :sub-jobs="project.sub_jobs || []"
      :create-sub-job="createSubJob"
      :approve-sub-job="approveSubJob"
      :deny-sub-job="denySubJob"
      :accept-submission="acceptSubmission"
      :reject-submission="rejectSubmission"
      :reauthorize-escrow="reauthorizeEscrow"
      :detach-escrow="detachEscrow"
      :load-activity="loadActivity"
      @refresh="emit('refresh')"
    />
  </section>
</template>

<style scoped>
.dashboard { display: grid; gap: 1.5rem; }
.eyebrow { margin: 0; text-transform: uppercase; letter-spacing: 0.06em; font-size: 0.75rem; color: #5c6b5a; }
h1 { margin: 0.2rem 0; font-size: 1.8rem; }
.scope, .budget { margin: 0; color: #445044; }
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
.row-actions { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem; }
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
</style>
