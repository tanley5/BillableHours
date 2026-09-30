<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import draggable from 'vuedraggable'

const props = defineProps({
  projectId: { type: [Number, String], required: true },
  assignments: { type: Array, default: () => [] },
  listContractors: { type: Function, required: true },
  assign: { type: Function, required: true },
})
const emit = defineEmits(['assigned', 'saved'])

const pool = ref([])
const pending = ref([])
const search = ref('')
const hourlyRate = ref('75.00')
const error = ref('')
const message = ref('')
const loading = ref(true)
const saving = ref(false)

const activeAssignments = computed(() =>
  (props.assignments || []).filter((a) => a.status === 'invited' || a.status === 'accepted'),
)

const activeContractorIds = computed(
  () => new Set(activeAssignments.value.map((a) => a.contractor?.id ?? a.contractor_id)),
)

const pendingIds = computed(() => new Set(pending.value.map((c) => c.id)))

const filteredPool = computed(() => {
  const q = search.value.trim().toLowerCase()
  return pool.value.filter((c) => {
    if (activeContractorIds.value.has(c.id) || pendingIds.value.has(c.id)) return false
    if (!q) return true
    return (c.name || '').toLowerCase().includes(q) || (c.email || '').toLowerCase().includes(q)
  })
})

async function loadPool({ clearError = true } = {}) {
  loading.value = true
  if (clearError) error.value = ''
  try {
    pool.value = await props.listContractors(props.projectId)
  } catch (err) {
    error.value = err.message || 'Could not load contractors.'
  } finally {
    loading.value = false
  }
}

onMounted(loadPool)
watch(
  () => props.projectId,
  () => {
    pending.value = []
    loadPool()
  },
)

function canDrag(c) {
  return c.connect_status === 'complete'
}

function onPoolClone(c) {
  if (!canDrag(c)) return false
  return { ...c }
}

function formatRate(c) {
  if (c.accept_rate == null) return 'No history'
  const pct = Math.round(Number(c.accept_rate) * 100)
  return `${pct}% accept · ${c.rejection_count} rejected`
}

function removePending(id) {
  pending.value = pending.value.filter((c) => c.id !== id)
}

async function save() {
  error.value = ''
  message.value = ''
  if (!pending.value.length) {
    error.value = 'Drag contractors into Assigned, then Save.'
    return
  }
  const rate = String(hourlyRate.value)
  if (!rate || Number(rate) <= 0) {
    error.value = 'Enter a valid hourly rate.'
    return
  }
  saving.value = true
  const remaining = []
  const succeeded = []
  for (const c of pending.value) {
    try {
      const assignment = await props.assign({
        contractor_id: c.id,
        hourly_rate: rate,
      })
      succeeded.push(assignment)
    } catch (err) {
      remaining.push(c)
      error.value = err.message || `Could not assign ${c.name}.`
    }
  }
  pending.value = remaining
  if (succeeded.length) {
    message.value = `Invited ${succeeded.length} contractor${succeeded.length === 1 ? '' : 's'}.`
    emit('saved', succeeded)
    for (const a of succeeded) emit('assigned', a)
    await loadPool({ clearError: false })
  }
  saving.value = false
}
</script>

<template>
  <section class="board" data-test="drag-assign-board">
    <header class="board-head">
      <h3>Assign contractors</h3>
      <p class="hint">
        Drag from the pool into Assigned, then Save to send invites (and fire notifications).
        Connect-incomplete contractors stay in the pool.
      </p>
    </header>

    <label class="search">
      Search pool
      <input v-model="search" type="search" placeholder="Filter by name or email" data-test="pool-search" />
    </label>

    <label class="rate">
      Hourly rate for new invites
      <input
        v-model="hourlyRate"
        name="hourly_rate"
        type="number"
        min="0.01"
        step="0.01"
        data-test="hourly-rate"
      />
    </label>

    <p v-if="loading" class="muted">Loading pool…</p>
    <div v-else class="columns">
      <div class="column">
        <h4>Pool</h4>
        <draggable
          :list="filteredPool"
          item-key="id"
          :group="{ name: 'contractors', pull: 'clone', put: false }"
          :clone="onPoolClone"
          :sort="false"
          class="drop-zone pool"
          data-test="pool-zone"
        >
          <template #item="{ element: c }">
            <article
              class="card"
              :class="{ blocked: !canDrag(c), elsewhere: c.assigned_elsewhere }"
              :data-test="`pool-card-${c.id}`"
            >
              <strong>{{ c.name }}</strong>
              <span class="badge reliability" :data-test="`reliability-${c.id}`">
                {{ formatRate(c) }}
              </span>
              <span v-if="c.assigned_elsewhere" class="marker">On other project</span>
              <span v-if="!canDrag(c)" class="marker warn">Connect incomplete</span>
            </article>
          </template>
        </draggable>
        <p v-if="!filteredPool.length" class="empty">No matching contractors.</p>
      </div>

      <div class="column">
        <h4>Assigned (pending save)</h4>
        <draggable
          v-model="pending"
          item-key="id"
          :group="{ name: 'contractors', pull: true, put: true }"
          class="drop-zone assigned"
          data-test="assigned-zone"
        >
          <template #item="{ element: c }">
            <article class="card pending" :data-test="`pending-card-${c.id}`">
              <strong>{{ c.name }}</strong>
              <button type="button" class="linkish" @click="removePending(c.id)">Remove</button>
            </article>
          </template>
        </draggable>
        <p v-if="!pending.length" class="empty">Drop contractors here.</p>

        <h4 class="active-title">Already on this project</h4>
        <ul class="active-list">
          <li v-for="a in activeAssignments" :key="a.id" :data-test="`active-${a.id}`">
            {{ a.contractor?.name }} · {{ a.status }}
          </li>
          <li v-if="!activeAssignments.length" class="empty">None yet.</li>
        </ul>
      </div>
    </div>

    <p v-if="error" class="error" data-test="board-error">{{ error }}</p>
    <p v-if="message" class="ok" data-test="board-message">{{ message }}</p>
    <button
      type="button"
      data-test="save-assignments"
      :disabled="saving || !pending.length"
      @click="save"
    >
      {{ saving ? 'Saving…' : 'Save invites' }}
    </button>
  </section>
</template>

<style scoped>
.board { display: grid; gap: 0.85rem; }
.board-head h3 { margin: 0 0 0.35rem; }
.hint { margin: 0; color: #5c6b5a; font-size: 0.9rem; }
.search, .rate { display: grid; gap: 0.3rem; font-weight: 600; max-width: 20rem; }
input {
  font: inherit;
  padding: 0.55rem 0.65rem;
  border: 1px solid #c5d0c4;
  border-radius: 0.4rem;
}
.columns {
  display: grid;
  gap: 1rem;
  grid-template-columns: 1fr 1fr;
}
@media (max-width: 720px) {
  .columns { grid-template-columns: 1fr; }
}
.column h4 { margin: 0 0 0.5rem; font-size: 0.95rem; }
.drop-zone {
  min-height: 8rem;
  border: 1px dashed #9aaf9a;
  border-radius: 0.5rem;
  padding: 0.5rem;
  display: grid;
  gap: 0.5rem;
  background: #f5f8f4;
}
.drop-zone.assigned { background: #eef4ec; border-style: solid; }
.card {
  background: #fff;
  border: 1px solid #c5d0c4;
  border-radius: 0.4rem;
  padding: 0.55rem 0.65rem;
  display: grid;
  gap: 0.25rem;
  cursor: grab;
}
.card.blocked { opacity: 0.55; cursor: not-allowed; }
.card.elsewhere { border-color: #b7a06a; }
.badge.reliability {
  font-size: 0.8rem;
  color: #3d5a45;
  font-weight: 600;
}
.marker { font-size: 0.75rem; color: #6b5a3a; }
.marker.warn { color: #8a2f1f; }
.active-title { margin-top: 1rem; }
.active-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 0.35rem; }
.empty, .muted { color: #5c6b5a; margin: 0; font-size: 0.9rem; }
.error { color: #8a2f1f; margin: 0; }
.ok { color: #1f3d2a; margin: 0; }
.linkish {
  background: none;
  border: none;
  color: #3d5a45;
  text-decoration: underline;
  padding: 0;
  font: inherit;
  cursor: pointer;
  justify-self: start;
}
button[data-test='save-assignments'] {
  font: inherit;
  padding: 0.65rem 0.9rem;
  border: none;
  border-radius: 0.4rem;
  background: #1f3d2a;
  color: #f4f7f2;
  font-weight: 700;
  justify-self: start;
}
button:disabled { opacity: 0.5; }
</style>
